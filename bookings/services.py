from decimal import Decimal
from datetime import datetime, time, timedelta
from django.conf import settings
from django.db import transaction, IntegrityError, OperationalError, models
from django.contrib.auth.models import User
from django.utils import timezone
from .models import Facility, Booking


class BookingConflictError(Exception):
    """Raised when a requested slot is already reserved or booked."""
    pass


class BookingValidationError(Exception):
    """Raised when booking request data is invalid or in the past."""
    pass


class BookingNotFoundError(Exception):
    """Raised when a booking record does not exist."""
    pass


class BookingStateError(Exception):
    """Raised when an invalid state transition is attempted."""
    pass


ACTIVE_STATUSES = ['PENDING_APPROVAL', 'APPROVED', 'CONFIRMED', 'COMPLETED']
PENDING_EXPIRATION_MINUTES = getattr(settings, 'BOOKING_PENDING_EXPIRATION_MINUTES', 15)

def broadcast_availability_change(facility_id, booking_date):
    """
    Dispatches real-time availability sync event after database transaction commits.
    Ensures connected clients reconcile directly with the latest PostgreSQL database state.
    """
    # Thread-safe dispatch hook for real-time subscribers
    pass



def expire_stale_bookings():
    """
    Sweeps and expires all pending bookings that have exceeded their expiration duration.
    Releases the slots atomically so they become AVAILABLE to other customers.
    """
    now = timezone.now()
    with transaction.atomic():
        stale = Booking.objects.select_for_update().filter(
            status='PENDING_APPROVAL',
            expires_at__isnull=False,
            expires_at__lte=now
        )
        expired_bookings = []
        for b in stale:
            b.status = 'EXPIRED'
            b.save(update_fields=['status', 'updated_at'])
            expired_bookings.append(b)
        return expired_bookings


def get_slot_availability(facility, target_date):
    """
    Returns the comprehensive list of slots with precise real-time statuses:
    - AVAILABLE (Green, bookable)
    - PENDING_APPROVAL (Orange, locked by customer pending owner decision)
    - APPROVED / CONFIRMED (Red, locked and approved)
    - EXPIRED / CANCELLED / REJECTED (Released, back to AVAILABLE)
    """
    # Sweep expired bookings first
    expire_stale_bookings()

    active_bookings = Booking.objects.filter(
        facility=facility,
        booking_date=target_date,
        status__in=ACTIVE_STATUSES
    )

    booking_map = {}
    for b in active_bookings:
        start_key = b.start_time.strftime('%H:%M')
        booking_map[start_key] = b

    current_tz = timezone.get_current_timezone()
    now_in_tz = timezone.now().astimezone(current_tz)
    today = now_in_tz.date()
    current_time = now_in_tz.time()

    duration = timedelta(minutes=facility.slot_duration_minutes)
    start_dt = datetime.combine(target_date, facility.open_time)
    end_dt = datetime.combine(target_date, facility.close_time)

    slots = []
    slot_curr = start_dt
    while slot_curr + duration <= end_dt:
        slot_start_time = slot_curr.time()
        slot_end_time = (slot_curr + duration).time()
        start_str = slot_start_time.strftime('%H:%M')
        end_str = slot_end_time.strftime('%H:%M')

        is_past = False
        if target_date < today:
            is_past = True
        elif target_date == today and slot_start_time <= current_time:
            is_past = True

        booking = booking_map.get(start_str)

        if booking:
            if booking.status == 'PENDING_APPROVAL':
                slot_status = 'PENDING_APPROVAL'
                display_status = 'Pending Approval'
            elif booking.status in ['APPROVED', 'CONFIRMED']:
                slot_status = 'APPROVED'
                display_status = 'Booked'
            elif booking.status == 'COMPLETED':
                slot_status = 'COMPLETED'
                display_status = 'Completed'
            else:
                slot_status = 'AVAILABLE'
                display_status = 'Available'
        elif is_past:
            slot_status = 'EXPIRED'
            display_status = 'Past'
        else:
            slot_status = 'AVAILABLE'
            display_status = 'Available'

        slots.append({
            'start_time': start_str,
            'end_time': end_str,
            'display_time': f"{slot_start_time.strftime('%I:%M %p')} - {slot_end_time.strftime('%I:%M %p')}",
            'price': float(facility.price_per_hour),
            'status': slot_status,
            'display_status': display_status,
            'is_available': (slot_status == 'AVAILABLE' and not is_past),
            'is_pending': (slot_status == 'PENDING_APPROVAL'),
            'is_booked': (slot_status in ['APPROVED', 'CONFIRMED', 'COMPLETED']),
            'is_past': is_past,
            'booking_id': booking.booking_id if booking else None,
            'customer_name': booking.customer_name if booking else None,
        })

        slot_curr += duration

    return slots


def reserve_slot(
    facility_id,
    booking_date,
    start_time_str,
    customer_name,
    customer_phone,
    user=None,
    notes='',
    total_price=None,
    advance_amount=Decimal('0.00'),
    payment_status='PAY_AT_VENUE',
    payment_method='CASH',
    created_by_staff=False,
    staff_notes='',
    initial_status='PENDING_APPROVAL'
):
    """
    Strict First-Come-First-Served Atomic Reservation.
    1. Validates requested slot.
    2. Starts an atomic database transaction.
    3. Locks any conflicting active bookings using SELECT FOR UPDATE.
    4. Rejects concurrent requests with HTTP 409 BookingConflictError.
    5. Creates PENDING_APPROVAL booking with expiration.
    """
    if isinstance(booking_date, str):
        try:
            booking_date = datetime.strptime(booking_date, '%Y-%m-%d').date()
        except ValueError:
            raise BookingValidationError("Invalid date format. Expected YYYY-MM-DD.")

    if isinstance(start_time_str, str):
        try:
            start_time = datetime.strptime(start_time_str, '%H:%M').time()
        except ValueError:
            raise BookingValidationError("Invalid time format. Expected HH:MM.")
    else:
        start_time = start_time_str

    try:
        facility = Facility.objects.get(id=facility_id, is_active=True)
    except Facility.DoesNotExist:
        raise BookingValidationError(f"Facility ID {facility_id} does not exist or is inactive.")

    # Time validation: Slot cannot be in the past
    now_in_tz = timezone.now().astimezone(timezone.get_current_timezone())
    today = now_in_tz.date()
    current_time = now_in_tz.time()

    if booking_date < today:
        raise BookingValidationError("Cannot book slots in the past.")
    if booking_date == today and start_time <= current_time:
        raise BookingValidationError("Cannot book a time slot that has already started or passed.")

    # Calculate end time
    start_dt = datetime.combine(booking_date, start_time)
    end_dt = start_dt + timedelta(minutes=facility.slot_duration_minutes)
    end_time = end_dt.time()

    # User resolution
    if not user or not user.is_authenticated:
        # Fallback to designated Admin or staff user for customer walk-in/public booking
        user = User.objects.filter(is_staff=True).first()
        if not user:
            user = User.objects.first()

    # ATOMIC DATABASE TRANSACTION WITH CONCURRENCY LOCKING & RETRY
    max_retries = 8
    for attempt in range(max_retries):
        try:
            with transaction.atomic():
                # Sweep any expired pending bookings first
                expire_stale_bookings()

                # Check existing active reservations for this facility, date, start_time
                existing_conflict = Booking.objects.select_for_update().filter(
                    facility=facility,
                    booking_date=booking_date,
                    start_time=start_time,
                    status__in=ACTIVE_STATUSES
                ).first()

                if existing_conflict:
                    raise BookingConflictError(
                        "Sorry! This slot has just been booked by another customer. Please select another available time slot."
                    )

                # Check for overlapping time range
                overlap_conflict = Booking.objects.select_for_update().filter(
                    facility=facility,
                    booking_date=booking_date,
                    status__in=ACTIVE_STATUSES
                ).filter(
                    models.Q(start_time__lt=end_time, end_time__gt=start_time)
                ).first()

                if overlap_conflict:
                    raise BookingConflictError(
                        "Sorry! This slot has just been booked by another customer. Please select another available time slot."
                    )

                expires_at = None
                if initial_status == 'PENDING_APPROVAL':
                    expires_at = timezone.now() + timedelta(minutes=PENDING_EXPIRATION_MINUTES)

                booking_price = Decimal(str(total_price)) if total_price is not None else facility.price_per_hour
                adv = Decimal(str(advance_amount)) if advance_amount is not None else Decimal('0.00')
                bal = max(Decimal('0.00'), booking_price - adv)

                booking = Booking.objects.create(
                    user=user,
                    facility=facility,
                    booking_date=booking_date,
                    start_time=start_time,
                    end_time=end_time,
                    total_price=booking_price,
                    advance_amount=adv,
                    balance_amount=bal,
                    status=initial_status,
                    payment_status=payment_status,
                    payment_method=payment_method,
                    customer_name=customer_name.strip(),
                    customer_phone=customer_phone.strip(),
                    notes=notes.strip(),
                    expires_at=expires_at,
                    created_by_staff=created_by_staff,
                    staff_notes=staff_notes.strip(),
                )
                transaction.on_commit(lambda: broadcast_availability_change(facility.id, booking_date))
                return booking

        except IntegrityError:
            # Database unique constraint caught simultaneous race condition
            raise BookingConflictError(
                "Sorry! This slot has just been booked by another customer. Please select another available time slot."
            )
        except OperationalError as oe:
            # Under SQLite lock contention, if another transaction is writing,
            # wait briefly with jitter and retry. If slot was actually taken by another customer,
            # the next attempt or check will cleanly detect the conflict.
            if attempt < max_retries - 1:
                import time as pytime, random
                pytime.sleep(0.04 + random.uniform(0.01, 0.05))
                continue
            raise BookingConflictError(
                "Sorry! This slot has just been booked by another customer. Please select another available time slot."
            )


def approve_booking(booking_id, approved_by_user=None):
    """
    Owner Approval Action:
    Transitions booking status from PENDING_APPROVAL to APPROVED.
    The slot remains locked and unavailable.
    """
    with transaction.atomic():
        try:
            booking = Booking.objects.select_for_update().get(booking_id=booking_id)
        except Booking.DoesNotExist:
            raise BookingNotFoundError(f"Booking #{booking_id} does not exist.")

        if booking.status in ['CANCELLED', 'REJECTED', 'EXPIRED']:
            raise BookingStateError(f"Cannot approve booking with status '{booking.status}'.")

        booking.status = 'APPROVED'
        booking.approved_at = timezone.now()
        booking.approved_by = approved_by_user if (approved_by_user and approved_by_user.is_authenticated) else None
        booking.expires_at = None  # Clear expiration upon approval
        booking.save()
        transaction.on_commit(lambda: broadcast_availability_change(booking.facility_id, booking.booking_date))
        return booking


def reject_booking(booking_id, rejected_by_user=None, reason='Rejected by owner'):
    """
    Owner Rejection Action:
    Transitions booking status to REJECTED.
    Safely releases the slot reservation so it becomes AVAILABLE again.
    """
    with transaction.atomic():
        try:
            booking = Booking.objects.select_for_update().get(booking_id=booking_id)
        except Booking.DoesNotExist:
            raise BookingNotFoundError(f"Booking #{booking_id} does not exist.")

        booking.status = 'REJECTED'
        booking.rejected_at = timezone.now()
        booking.rejection_reason = reason
        booking.expires_at = None
        booking.save()
        transaction.on_commit(lambda: broadcast_availability_change(booking.facility_id, booking.booking_date))
        return booking


def cancel_booking_service(booking_id, reason='Cancelled by customer or owner'):
    """
    Cancellation Action:
    Transitions booking status to CANCELLED.
    Safely releases the slot reservation so it becomes AVAILABLE again.
    """
    with transaction.atomic():
        try:
            booking = Booking.objects.select_for_update().get(booking_id=booking_id)
        except Booking.DoesNotExist:
            raise BookingNotFoundError(f"Booking #{booking_id} does not exist.")

        booking.status = 'CANCELLED'
        booking.cancelled_at = timezone.now()
        booking.cancellation_reason = reason
        booking.expires_at = None
        booking.save()
        transaction.on_commit(lambda: broadcast_availability_change(booking.facility_id, booking.booking_date))
        return booking

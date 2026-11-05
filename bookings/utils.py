from datetime import datetime, time, timedelta
from django.utils import timezone
from .models import Booking


def generate_slots_for_date(facility, target_date):
    """
    Generates all slots for a given facility on target_date,
    annotating each with status, is_pending, is_booked, and is_past.
    """
    from .services import expire_stale_bookings, ACTIVE_STATUSES
    expire_stale_bookings()

    slots = []
    
    # Existing active bookings for this facility and date
    active_bookings = Booking.objects.filter(
        facility=facility,
        booking_date=target_date,
        status__in=ACTIVE_STATUSES
    )
    
    booking_map = {b.start_time: b for b in active_bookings}

    current_tz = timezone.get_current_timezone()
    now_in_tz = timezone.now().astimezone(current_tz)
    today = now_in_tz.date()
    current_time = now_in_tz.time()

    # Create slots in increments of facility.slot_duration_minutes
    duration = timedelta(minutes=facility.slot_duration_minutes)
    
    # Build start datetime for the loop
    start_dt = datetime.combine(target_date, facility.open_time)
    end_dt = datetime.combine(target_date, facility.close_time)

    slot_curr = start_dt
    while slot_curr + duration <= end_dt:
        slot_start_time = slot_curr.time()
        slot_end_time = (slot_curr + duration).time()

        is_past = False
        if target_date < today:
            is_past = True
        elif target_date == today and slot_start_time <= current_time:
            is_past = True

        booking = booking_map.get(slot_start_time)
        is_pending = bool(booking and booking.status == 'PENDING_APPROVAL')
        is_booked = bool(booking and booking.status in ['APPROVED', 'CONFIRMED', 'COMPLETED'])
        is_available = (not booking) and (not is_past)

        status_label = 'AVAILABLE'
        if is_pending:
            status_label = 'PENDING_APPROVAL'
        elif is_booked:
            status_label = 'APPROVED'
        elif is_past:
            status_label = 'EXPIRED'

        slots.append({
            'start_time': slot_start_time.strftime('%H:%M'),
            'end_time': slot_end_time.strftime('%H:%M'),
            'display_time': f"{slot_start_time.strftime('%I:%M %p')} - {slot_end_time.strftime('%I:%M %p')}",
            'price': float(facility.price_per_hour),
            'status': status_label,
            'is_pending': is_pending,
            'is_booked': is_booked,
            'is_past': is_past,
            'is_available': is_available,
            'booking': booking,
        })

        slot_curr += duration

    return slots

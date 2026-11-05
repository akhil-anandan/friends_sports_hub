import json
from datetime import datetime
from decimal import Decimal
from django.http import JsonResponse, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import user_passes_test
from django.utils import timezone
from django.db import IntegrityError, OperationalError
from .models import Facility, Booking
from .services import (
    reserve_slot,
    approve_booking,
    reject_booking,
    cancel_booking_service,
    get_slot_availability,
    expire_stale_bookings,
    BookingConflictError,
    BookingValidationError,
    BookingNotFoundError,
    BookingStateError,
    ACTIVE_STATUSES,
)


def no_cache_json(data, status=200):
    res = JsonResponse(data, status=status)
    res['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    res['Pragma'] = 'no-cache'
    res['Expires'] = '0'
    return res


def api_health_check(request):
    """
    Production Health Endpoint.
    Verifies backend operational status and database connection.
    """
    from django.db import connection
    db_status = 'disconnected'
    db_engine = connection.vendor
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1;')
            if cursor.fetchone():
                db_status = 'connected'
    except Exception as e:
        db_status = f'error: {str(e)}'

    return no_cache_json({
        'status': 'ok' if db_status == 'connected' else 'degraded',
        'database_engine': db_engine,
        'database_status': db_status,
        'timestamp': timezone.now().isoformat()
    }, status=200 if db_status == 'connected' else 503)


def is_staff_user(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)


@csrf_exempt
def api_reserve_slot(request):
    """
    Public First-Come-First-Served Reservation Endpoint.
    Returns HTTP 201 on success, HTTP 409 Conflict if already reserved.
    """
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        data = request.POST

    facility_id = data.get('facility_id')
    facility_slug = data.get('facility_slug')
    date_str = data.get('date') or data.get('booking_date')
    start_time_str = data.get('start_time') or data.get('time')
    customer_name = data.get('customer_name', '').strip()
    customer_phone = data.get('customer_phone', '').strip()
    notes = data.get('notes', '').strip()

    if not facility_id and facility_slug:
        fac = Facility.objects.filter(slug=facility_slug, is_active=True).first()
        if fac:
            facility_id = fac.id

    if not all([facility_id, date_str, start_time_str, customer_name, customer_phone]):
        return no_cache_json({
            'success': False,
            'error': 'validation',
            'message': 'Please provide all required fields: facility, date, start_time, customer_name, customer_phone.'
        }, status=400)

    try:
        booking = reserve_slot(
            facility_id=facility_id,
            booking_date=date_str,
            start_time_str=start_time_str,
            customer_name=customer_name,
            customer_phone=customer_phone,
            user=request.user if request.user.is_authenticated else None,
            notes=notes,
            initial_status='PENDING_APPROVAL'
        )
        return no_cache_json({
            'success': True,
            'booking_id': booking.booking_id,
            'status': booking.status,
            'facility_name': booking.facility.name,
            'facility_slug': booking.facility.slug,
            'date': booking.booking_date.strftime('%Y-%m-%d'),
            'start_time': booking.start_time.strftime('%H:%M'),
            'end_time': booking.end_time.strftime('%H:%M'),
            'display_time': f"{booking.start_time.strftime('%I:%M %p')} - {booking.end_time.strftime('%I:%M %p')}",
            'customer_name': booking.customer_name,
            'customer_phone': booking.customer_phone,
            'total_price': float(booking.total_price),
            'expires_at': booking.expires_at.isoformat() if booking.expires_at else None,
            'message': 'Slot temporarily reserved with PENDING OWNER APPROVAL status.'
        }, status=201)

    except (BookingConflictError, IntegrityError, OperationalError) as e:
        msg = str(e)
        if isinstance(e, (IntegrityError, OperationalError)) or not msg:
            msg = "Sorry! This slot has just been booked by another customer. Please select another available time slot."
        return no_cache_json({
            'success': False,
            'error': 'conflict',
            'message': msg
        }, status=409)

    except BookingValidationError as e:
        return no_cache_json({
            'success': False,
            'error': 'validation',
            'message': str(e)
        }, status=400)

    except Exception as e:
        return no_cache_json({
            'success': False,
            'error': 'server_error',
            'message': f"Unexpected reservation error: {str(e)}"
        }, status=500)


def api_get_availability(request):
    """
    Public Endpoint: Dynamic Slot Availability.
    Sweeps expired reservations and returns current real-time statuses.
    """
    facility_id = request.GET.get('facility_id')
    facility_slug = request.GET.get('facility_slug')
    date_str = request.GET.get('date')

    if not date_str:
        date_str = timezone.localdate().strftime('%Y-%m-%d')

    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return no_cache_json({'success': False, 'error': 'Invalid date format. Expected YYYY-MM-DD.'}, status=400)

    if facility_id:
        facility = Facility.objects.filter(id=facility_id, is_active=True).first()
    elif facility_slug:
        facility = Facility.objects.filter(slug=facility_slug, is_active=True).first()
    else:
        facility = Facility.objects.filter(slug='turf', is_active=True).first() or Facility.objects.filter(is_active=True).first()

    if not facility:
        return no_cache_json({'success': False, 'error': 'Facility not found'}, status=404)

    slots = get_slot_availability(facility, target_date)
    available_count = sum(1 for s in slots if s['is_available'])
    pending_count = sum(1 for s in slots if s['is_pending'])
    booked_count = sum(1 for s in slots if s['is_booked'])

    return no_cache_json({
        'success': True,
        'facility_id': facility.id,
        'facility_name': facility.name,
        'facility_slug': facility.slug,
        'date': date_str,
        'available_count': available_count,
        'pending_count': pending_count,
        'booked_count': booked_count,
        'slots': slots,
    })


@csrf_exempt
def api_approve_booking(request, booking_id):
    """
    Owner/Staff Action: Approve pending booking.
    """
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    # Check permission or admin session
    is_admin = is_staff_user(request.user)
    if not is_admin:
        # Check custom header or body token for API/Staff clients
        admin_token = request.headers.get('X-Admin-Auth') or request.POST.get('admin_token')
        if admin_token == 'admin1010':
            is_admin = True

    if not is_admin:
        return no_cache_json({'success': False, 'error': 'unauthorized', 'message': 'Owner authentication required.'}, status=403)

    try:
        booking = approve_booking(booking_id, approved_by_user=request.user if request.user.is_authenticated else None)
        return no_cache_json({
            'success': True,
            'booking_id': booking.booking_id,
            'status': booking.status,
            'message': f"Booking #{booking.booking_id} has been APPROVED and marked as BOOKED."
        })
    except BookingNotFoundError as e:
        return no_cache_json({'success': False, 'error': 'not_found', 'message': str(e)}, status=404)
    except BookingStateError as e:
        return no_cache_json({'success': False, 'error': 'invalid_state', 'message': str(e)}, status=400)


@csrf_exempt
def api_reject_booking(request, booking_id):
    """
    Owner/Staff Action: Reject booking, immediately releasing the slot to AVAILABLE.
    """
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    is_admin = is_staff_user(request.user)
    if not is_admin:
        admin_token = request.headers.get('X-Admin-Auth') or request.POST.get('admin_token')
        if admin_token == 'admin1010':
            is_admin = True

    if not is_admin:
        return no_cache_json({'success': False, 'error': 'unauthorized', 'message': 'Owner authentication required.'}, status=403)

    reason = request.POST.get('reason', 'Rejected by owner')
    try:
        booking = reject_booking(booking_id, rejected_by_user=request.user if request.user.is_authenticated else None, reason=reason)
        return no_cache_json({
            'success': True,
            'booking_id': booking.booking_id,
            'status': booking.status,
            'message': f"Booking #{booking.booking_id} has been REJECTED. The slot is released and AVAILABLE."
        })
    except BookingNotFoundError as e:
        return no_cache_json({'success': False, 'error': 'not_found', 'message': str(e)}, status=404)


@csrf_exempt
def api_cancel_booking(request, booking_id):
    """
    Cancel booking and release slot.
    """
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    reason = request.POST.get('reason', 'Cancelled')
    try:
        booking = cancel_booking_service(booking_id, reason=reason)
        return no_cache_json({
            'success': True,
            'booking_id': booking.booking_id,
            'status': booking.status,
            'message': f"Booking #{booking.booking_id} has been CANCELLED. The slot is released and AVAILABLE."
        })
    except BookingNotFoundError as e:
        return no_cache_json({'success': False, 'error': 'not_found', 'message': str(e)}, status=404)


def api_sweep_expired(request):
    """
    Triggers automated expiration sweep.
    """
    expired = expire_stale_bookings()
    return no_cache_json({
        'success': True,
        'expired_count': len(expired),
        'expired_booking_ids': [b.booking_id for b in expired]
    })

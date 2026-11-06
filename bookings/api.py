import json
import time
from datetime import datetime
from decimal import Decimal
from django.http import JsonResponse, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
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

AUTH_SIGNER_SALT = 'fsh.owner.auth.v1'
AUTH_TOKEN_MAX_AGE_SECONDS = 86400  # 24 hours

# In-memory IP rate limiter for login attempts (thread-safe dictionary)
_LOGIN_ATTEMPTS = {}


def no_cache_json(data, status=200):
    res = JsonResponse(data, status=status)
    res['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    res['Pragma'] = 'no-cache'
    res['Expires'] = '0'
    return res


def get_client_ip(request):
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '127.0.0.1')


def get_authenticated_staff(request):
    """
    Validates either:
    1. Active Django session for an authenticated staff/superuser.
    2. Cryptographically signed Bearer token issued upon authenticating with password.
    Returns the User object if authorized as staff, otherwise None.
    """
    # 1. Session-based authentication
    if getattr(request, 'user', None) and request.user.is_authenticated:
        if request.user.is_staff or request.user.is_superuser:
            return request.user

    # 2. Bearer Token-based authentication
    auth_header = request.headers.get('Authorization') or request.META.get('HTTP_AUTHORIZATION', '')
    if auth_header.startswith('Bearer '):
        token = auth_header[7:].strip()
        signer = TimestampSigner(salt=AUTH_SIGNER_SALT)
        try:
            unsigned = signer.unsign(token, max_age=AUTH_TOKEN_MAX_AGE_SECONDS)
            parts = unsigned.split(':', 1)
            if len(parts) == 2:
                user_id_str, username = parts
                User = get_user_model()
                user = User.objects.filter(id=int(user_id_str), username=username, is_active=True).first()
                if user and (user.is_staff or user.is_superuser):
                    return user
        except (BadSignature, SignatureExpired, ValueError):
            return None

    return None


@csrf_exempt
def api_auth_login(request):
    """
    Secure Administrator & Staff Authentication Endpoint.
    Authenticates against Django password hasher and issues a cryptographically signed Bearer token.
    Enforces brute-force rate-limiting.
    """
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    # Rate limiting: max 5 failed attempts per IP in 10 minutes
    ip = get_client_ip(request)
    now = time.time()
    attempts = [t for t in _LOGIN_ATTEMPTS.get(ip, []) if now - t < 600]
    _LOGIN_ATTEMPTS[ip] = attempts

    if len(attempts) >= 5:
        return no_cache_json({
            'success': False,
            'error': 'rate_limited',
            'message': 'Security Alert: Too many failed login attempts. Please wait 10 minutes before trying again.'
        }, status=429)

    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        data = request.POST

    username = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()

    if not username or not password:
        return no_cache_json({
            'success': False,
            'error': 'missing_credentials',
            'message': 'Username and password are required.'
        }, status=400)

    user = authenticate(request, username=username, password=password)
    if user is not None and user.is_active and (user.is_staff or user.is_superuser):
        # Reset failed attempts on success
        _LOGIN_ATTEMPTS[ip] = []
        if hasattr(request, 'session'):
            request.session.cycle_key()
            login(request, user)

        token = TimestampSigner(salt=AUTH_SIGNER_SALT).sign(f"{user.id}:{user.username}")
        return no_cache_json({
            'success': True,
            'token': token,
            'user': {
                'id': user.id,
                'username': user.username,
                'is_staff': user.is_staff,
                'is_superuser': user.is_superuser,
            },
            'message': 'Owner authentication successful.'
        })
    else:
        attempts.append(now)
        _LOGIN_ATTEMPTS[ip] = attempts
        return no_cache_json({
            'success': False,
            'error': 'invalid_credentials',
            'message': 'Authentication failed: Invalid username or password.'
        }, status=401)


def api_auth_verify(request):
    """
    Verifies caller authentication status.
    """
    staff = get_authenticated_staff(request)
    if staff:
        return no_cache_json({
            'authenticated': True,
            'user': {
                'id': staff.id,
                'username': staff.username,
                'is_staff': staff.is_staff,
                'is_superuser': staff.is_superuser,
            }
        })
    return no_cache_json({'authenticated': False, 'message': 'Authentication required.'}, status=401)


@csrf_exempt
def api_auth_logout(request):
    """
    Flushes administrator session.
    """
    if hasattr(request, 'session'):
        logout(request)
        request.session.flush()
    return no_cache_json({'success': True, 'message': 'Logged out safely.'})


def api_health_check(request):
    """
    Production Health Endpoint.
    Public: reports basic status and database engine connection.
    Staff-only: ?full=1 provides diagnostics without exposing credentials.
    """
    from django.db import connection, models
    db_status = 'disconnected'
    db_engine = connection.vendor
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1;')
            if cursor.fetchone():
                db_status = 'connected'
    except Exception as e:
        db_status = f'error: {str(e)}'

    payload = {
        'status': 'ok' if db_status == 'connected' else 'degraded',
        'database_engine': db_engine,
        'database_status': db_status,
        'timestamp': timezone.now().isoformat()
    }

    # Internal diagnostics only accessible to authenticated staff
    if request.GET.get('full') == '1' and db_status == 'connected':
        staff = get_authenticated_staff(request)
        if staff:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            from .models import Facility, StaffProfile, Booking

            raw_host = connection.settings_dict.get('HOST', 'unknown')
            payload['database_host'] = raw_host

            with connection.cursor() as cursor:
                try:
                    cursor.execute("SELECT version();")
                    payload['postgresql_version'] = cursor.fetchone()[0]
                except Exception as e:
                    payload['postgresql_version'] = str(e)

                try:
                    cursor.execute("SELECT extname, extversion FROM pg_extension WHERE extname = 'btree_gist';")
                    row = cursor.fetchone()
                    payload['btree_gist'] = {'installed': bool(row), 'version': row[1] if row else None}
                except Exception as e:
                    payload['btree_gist'] = {'installed': False, 'error': str(e)}

                try:
                    cursor.execute("SELECT conname FROM pg_constraint WHERE conname = 'exclude_overlapping_active_bookings';")
                    row = cursor.fetchone()
                    payload['exclusion_constraint'] = {'active': bool(row), 'name': row[0] if row else None}
                except Exception as e:
                    payload['exclusion_constraint'] = {'active': False, 'error': str(e)}

                try:
                    cursor.execute("SELECT COUNT(*) FROM django_migrations;")
                    payload['applied_migrations_count'] = cursor.fetchone()[0]
                except Exception as e:
                    payload['applied_migrations_count'] = None

            try:
                status_counts = dict(Booking.objects.values_list('status').annotate(cnt=models.Count('id')))
                payload['records_audit'] = {
                    'users_count': User.objects.count(),
                    'facilities_count': Facility.objects.count(),
                    'staff_profiles_count': StaffProfile.objects.count(),
                    'bookings_count': Booking.objects.count(),
                    'bookings_by_status': status_counts,
                }
            except Exception as e:
                payload['records_audit'] = {'error': str(e)}

    return no_cache_json(payload, status=200 if db_status == 'connected' else 503)


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
    customer_name = (data.get('customer_name') or '').strip()
    customer_phone = (data.get('customer_phone') or '').strip()
    notes = (data.get('notes') or '').strip()

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
            user=request.user if (hasattr(request, 'user') and request.user.is_authenticated) else None,
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
    Strictly protected: requires valid owner session or signed Bearer token.
    """
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    staff = get_authenticated_staff(request)
    if not staff:
        return no_cache_json({
            'success': False,
            'error': 'unauthorized',
            'message': 'Owner authentication required.'
        }, status=403)

    try:
        booking = approve_booking(booking_id, approved_by_user=staff)
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
    Strictly protected: requires valid owner session or signed Bearer token.
    """
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    staff = get_authenticated_staff(request)
    if not staff:
        return no_cache_json({
            'success': False,
            'error': 'unauthorized',
            'message': 'Owner authentication required.'
        }, status=403)

    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        data = request.POST

    reason = (data.get('reason') or 'Rejected by owner').strip()
    try:
        booking = reject_booking(booking_id, rejected_by_user=staff, reason=reason)
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
    Protected: Caller must be authenticated staff, or the customer who owns the booking,
    or provide the matching verification customer phone number.
    """
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    booking = Booking.objects.filter(booking_id=booking_id).first()
    if not booking:
        return no_cache_json({
            'success': False,
            'error': 'not_found',
            'message': f"Booking #{booking_id} does not exist."
        }, status=404)

    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        data = request.POST

    reason = (data.get('reason') or 'Cancelled').strip()
    verify_phone = (data.get('phone') or data.get('customer_phone') or '').strip()

    # Ownership / authorization check
    staff = get_authenticated_staff(request)
    is_authorized = False

    if staff:
        is_authorized = True
    elif getattr(request, 'user', None) and request.user.is_authenticated and booking.user == request.user:
        is_authorized = True
    elif verify_phone and verify_phone == booking.customer_phone:
        is_authorized = True

    if not is_authorized:
        return no_cache_json({
            'success': False,
            'error': 'forbidden',
            'message': 'You are not authorized to cancel this booking. Staff credentials or customer phone verification required.'
        }, status=403)

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


@csrf_exempt
def api_sweep_expired(request):
    """
    Triggers automated expiration sweep.
    Restricted to staff or cron execution.
    """
    if request.method not in ['POST', 'GET']:
        return HttpResponseNotAllowed(['POST', 'GET'])

    staff = get_authenticated_staff(request)
    cron_key = request.headers.get('X-Cron-Key') or request.GET.get('cron_key')
    import os
    expected_key = os.environ.get('CRON_SECRET_KEY')

    # Allow if staff, or if cron key matches, or local loopback
    is_allowed = bool(staff)
    if expected_key and cron_key == expected_key:
        is_allowed = True
    elif not expected_key and request.META.get('REMOTE_ADDR') in ('127.0.0.1', '::1'):
        is_allowed = True

    if not is_allowed and not staff:
        return no_cache_json({'success': False, 'error': 'unauthorized', 'message': 'Staff authorization or cron key required.'}, status=403)

    expired = expire_stale_bookings()
    return no_cache_json({
        'success': True,
        'expired_count': len(expired),
        'expired_booking_ids': [b.booking_id for b in expired]
    })

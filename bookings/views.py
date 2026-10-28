import re
import urllib.parse
from decimal import Decimal
from datetime import datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.db import transaction
from django.utils import timezone
from .models import Facility, Booking
from .utils import generate_slots_for_date
from .whatsapp import clean_whatsapp_phone, build_confirmation_message, send_whatsapp_server_side

# Business contact info for WhatsApp / Call
OWNER_PHONE = '6238006820'
WHATSAPP_PHONE = '916238006820'  # International format for WhatsApp


def is_staff_user(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)


staff_required = user_passes_test(is_staff_user, login_url='/login/')


def booking_view(request, slug=None):
    """
    Public slot availability page. Shows vacant/booked slots.
    Users can see slots and call/WhatsApp the owner to book.
    Only admin can actually confirm a booking.
    """
    facilities = Facility.objects.filter(is_active=True)

    if slug:
        selected_facility = get_object_or_404(Facility, slug=slug, is_active=True)
    else:
        selected_facility = facilities.filter(slug='turf').first() or facilities.first()

    today_str = timezone.localdate().strftime('%Y-%m-%d')
    date_str = request.GET.get('date', today_str)

    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        target_date = timezone.localdate()
        date_str = today_str

    min_date = timezone.localdate()
    max_date = min_date + timedelta(days=30)
    if target_date < min_date:
        target_date = min_date
        date_str = min_date.strftime('%Y-%m-%d')
    elif target_date > max_date:
        target_date = max_date
        date_str = max_date.strftime('%Y-%m-%d')

    slots = []
    if selected_facility:
        slots = generate_slots_for_date(selected_facility, target_date)

    context = {
        'facilities': facilities,
        'selected_facility': selected_facility,
        'target_date': target_date,
        'date_str': date_str,
        'min_date': min_date.strftime('%Y-%m-%d'),
        'max_date': max_date.strftime('%Y-%m-%d'),
        'slots': slots,
        'owner_phone': OWNER_PHONE,
        'whatsapp_phone': WHATSAPP_PHONE,
    }
    return render(request, 'bookings/book_slot.html', context)


def check_slots_api(request):
    """
    AJAX endpoint returning dynamic slot availability.
    """
    facility_id = request.GET.get('facility_id')
    date_str = request.GET.get('date')

    if not facility_id or not date_str:
        return JsonResponse({'success': False, 'error': 'Missing parameters'}, status=400)

    try:
        facility = Facility.objects.get(id=facility_id, is_active=True)
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except (Facility.DoesNotExist, ValueError):
        return JsonResponse({'success': False, 'error': 'Invalid facility or date'}, status=400)

    slots = generate_slots_for_date(facility, target_date)
    return JsonResponse({
        'success': True,
        'facility_name': facility.name,
        'date': date_str,
        'price_per_hour': float(facility.price_per_hour),
        'slots': slots,
    })


@staff_required
def confirm_booking(request):
    """
    Admin/Staff only: Confirms a slot booking directly without any payment.
    Captures customer name, club name (notes), and phone number.
    """
    if request.method != 'POST':
        return redirect('book_slot')

    facility_id = request.POST.get('facility_id')
    date_str = request.POST.get('booking_date')
    start_time_str = request.POST.get('start_time')
    customer_name = request.POST.get('customer_name', '').strip()
    customer_phone = request.POST.get('customer_phone', '').strip()
    notes = request.POST.get('notes', '').strip()  # Used for club name / notes

    if not all([facility_id, date_str, start_time_str, customer_name, customer_phone]):
        messages.error(request, "Please fill in all required fields: customer name, phone, and time slot.")
        return redirect('book_slot')

    facility = get_object_or_404(Facility, id=facility_id, is_active=True)

    try:
        booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        start_time = datetime.strptime(start_time_str, '%H:%M').time()
    except ValueError:
        messages.error(request, "Invalid date or time format.")
        return redirect('book_slot')

    # Compute end time
    start_dt = datetime.combine(booking_date, start_time)
    end_dt = start_dt + timedelta(minutes=facility.slot_duration_minutes)
    end_time = end_dt.time()

    # ATOMIC TRANSACTION TO PREVENT OVERLAPPING / RACE CONDITIONS
    with transaction.atomic():
        conflict_exists = Booking.objects.select_for_update().filter(
            facility=facility,
            booking_date=booking_date,
            start_time=start_time
        ).exclude(status='CANCELLED').exists()

        if conflict_exists:
            messages.error(request, f"Slot {start_time_str} on {date_str} is already booked. Please select another time.")
            return redirect('book_slot')

        booking = Booking.objects.create(
            user=request.user,
            facility=facility,
            booking_date=booking_date,
            start_time=start_time,
            end_time=end_time,
            total_price=facility.price_per_hour,
            advance_amount=Decimal('0.00'),
            balance_amount=facility.price_per_hour,
            status='CONFIRMED',
            payment_status='PAY_AT_VENUE',
            payment_method='CASH',
            customer_name=customer_name,
            customer_phone=customer_phone,
            customer_email='',
            notes=notes,
            created_by_staff=True,
            staff_notes=f"Booked by admin: {request.user.username}",
        )

    # 1. Attempt server-side automated dispatch if gateway is configured
    msg_text = build_confirmation_message(booking)
    sent, _ = send_whatsapp_server_side(booking.customer_phone, msg_text)

    if sent:
        messages.success(request, f"✅ Slot booked and confirmation sent automatically to {customer_name} on WhatsApp!")
        return redirect('booking_detail', booking_id=booking.booking_id)

    # 2. Otherwise redirect to voucher with auto_send=1 to auto-launch WhatsApp
    messages.success(request, f"✅ Slot confirmed for {customer_name}! Booking ID: {booking.booking_id}")
    return redirect(f"/booking/{booking.booking_id}/?auto_send=1")


def booking_detail(request, booking_id):
    """
    Renders receipt and details for a specific booking. Admin/staff only.
    Generates pre-formatted direct WhatsApp URLs for customer and owner.
    """
    booking = get_object_or_404(Booking, booking_id=booking_id)

    if not (request.user.is_authenticated and (request.user.is_staff or request.user == booking.user)):
        return redirect('login')

    customer_phone_clean = clean_whatsapp_phone(booking.customer_phone)
    owner_phone_clean = '916238006820'

    confirmation_text = build_confirmation_message(booking)
    encoded_text = urllib.parse.quote(confirmation_text)

    if customer_phone_clean:
        customer_wa_url = f"https://api.whatsapp.com/send?phone={customer_phone_clean}&text={encoded_text}"
        customer_wa_short = f"https://wa.me/{customer_phone_clean}?text={encoded_text}"
    else:
        customer_wa_url = f"https://api.whatsapp.com/send?text={encoded_text}"
        customer_wa_short = f"https://wa.me/?text={encoded_text}"

    owner_wa_url = f"https://api.whatsapp.com/send?phone={owner_phone_clean}&text={encoded_text}"

    context = {
        'booking': booking,
        'customer_phone_clean': customer_phone_clean,
        'customer_wa_url': customer_wa_url,
        'customer_wa_short': customer_wa_short,
        'owner_wa_url': owner_wa_url,
        'confirmation_text': confirmation_text,
        'encoded_text': encoded_text,
    }
    return render(request, 'bookings/booking_detail.html', context)


@staff_required
def cancel_booking(request, booking_id):
    """
    Admin/Staff: Cancel a booking.
    """
    booking = get_object_or_404(Booking, booking_id=booking_id)

    if not booking.is_cancellable:
        messages.error(request, "This booking cannot be cancelled because it has already started or concluded.")
        return redirect('staff_dashboard')

    if request.method == 'POST':
        reason = request.POST.get('cancellation_reason', 'Cancelled by admin').strip()
        booking.status = 'CANCELLED'
        booking.cancellation_reason = reason
        booking.cancelled_at = timezone.now()
        booking.save()

        messages.success(request, f"Booking #{booking.booking_id} has been cancelled. Slot is now free.")
        return redirect('staff_dashboard')

    return render(request, 'bookings/cancel_confirm.html', {'booking': booking})

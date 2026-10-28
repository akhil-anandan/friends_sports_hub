from decimal import Decimal
from datetime import datetime, time, timedelta
from django.shortcuts import render, redirect, get_object_or_404

from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, Count, Q
from django.utils import timezone
from .models import Facility, Booking, StaffProfile
from .utils import generate_slots_for_date
from .whatsapp import build_confirmation_message, send_whatsapp_server_side


def is_staff_user(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)


def is_owner_user(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return hasattr(user, 'staff_profile') and user.staff_profile.role == 'OWNER'


staff_required = user_passes_test(is_staff_user, login_url='/login/')
owner_required = user_passes_test(is_owner_user, login_url='/manage/')


@staff_required
def staff_dashboard_view(request):
    """
    Main operational portal for turf owner and booking staff.
    """
    today_str = timezone.localdate().strftime('%Y-%m-%d')
    date_str = request.GET.get('date', today_str)

    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        selected_date = timezone.localdate()
        date_str = today_str

    facility_slug = request.GET.get('facility')
    facilities = Facility.objects.filter(is_active=True)
    
    # Query bookings for this day
    bookings_qs = Booking.objects.filter(booking_date=selected_date).select_related('facility', 'user')
    if facility_slug:
        bookings_qs = bookings_qs.filter(facility__slug=facility_slug)

    # Search filter by customer name, phone, or reference
    q = request.GET.get('q', '').strip()
    if q:
        bookings_qs = bookings_qs.filter(
            Q(booking_id__icontains=q) |
            Q(customer_name__icontains=q) |
            Q(customer_phone__icontains=q)
        )

    # Calculate KPIs for selected date
    confirmed_bookings = bookings_qs.filter(status='CONFIRMED')
    completed_bookings = bookings_qs.filter(status='COMPLETED')
    cancelled_bookings = bookings_qs.filter(status='CANCELLED')

    total_revenue_expected = confirmed_bookings.aggregate(Sum('total_price'))['total_price__sum'] or 0
    full_paid = confirmed_bookings.filter(payment_status='PAID').aggregate(Sum('total_price'))['total_price__sum'] or 0
    advance_paid = confirmed_bookings.filter(payment_status='ADVANCE_PAID').aggregate(Sum('advance_amount'))['advance_amount__sum'] or 0
    total_revenue_paid = full_paid + advance_paid
    total_revenue_pending = confirmed_bookings.aggregate(Sum('balance_amount'))['balance_amount__sum'] or 0


    # Hourly match schedule grid for the primary turf (or selected facility)
    primary_facility = facilities.filter(slug=facility_slug).first() or facilities.filter(slug='turf').first() or facilities.first()
    schedule_slots = []
    if primary_facility:
        schedule_slots = generate_slots_for_date(primary_facility, selected_date)
        # Attach active booking object to each slot if booked
        active_day_bookings = {b.start_time.strftime('%H:%M'): b for b in Booking.objects.filter(facility=primary_facility, booking_date=selected_date).exclude(status='CANCELLED')}
        for s in schedule_slots:
            s['booking'] = active_day_bookings.get(s['start_time'])

    is_owner = is_owner_user(request.user)

    context = {
        'selected_date': selected_date,
        'date_str': date_str,
        'facilities': facilities,
        'selected_facility': primary_facility,
        'facility_slug': facility_slug,
        'bookings': bookings_qs.order_by('start_time'),
        'total_confirmed_count': confirmed_bookings.count(),
        'total_completed_count': completed_bookings.count(),
        'total_cancelled_count': cancelled_bookings.count(),
        'total_revenue_expected': total_revenue_expected,
        'total_revenue_paid': total_revenue_paid,
        'total_revenue_pending': total_revenue_pending,
        'schedule_slots': schedule_slots,
        'is_owner': is_owner,
        'search_query': q,
    }
    return render(request, 'bookings/staff_dashboard.html', context)


@staff_required
def staff_walkin_booking_view(request):
    """
    Allows ground staff or owner to enter an offline walk-in or phone call booking.
    """
    facilities = Facility.objects.filter(is_active=True)
    today_str = timezone.localdate().strftime('%Y-%m-%d')

    if request.method == 'POST':
        facility_id = request.POST.get('facility_id')
        date_str = request.POST.get('booking_date')
        start_time_str = request.POST.get('start_time')
        customer_name = request.POST.get('customer_name', '').strip()
        customer_phone = request.POST.get('customer_phone', '').strip()
        payment_status = request.POST.get('payment_status', 'PAID')
        staff_notes = request.POST.get('staff_notes', '').strip()

        if not all([facility_id, date_str, start_time_str, customer_name, customer_phone]):
            messages.error(request, "Please fill in all required customer and slot fields.")
            return redirect('staff_walkin_booking')

        facility = get_object_or_404(Facility, id=facility_id, is_active=True)

        try:
            booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            start_time = datetime.strptime(start_time_str, '%H:%M').time()
        except ValueError:
            messages.error(request, "Invalid date or time format.")
            return redirect('staff_walkin_booking')

        start_dt = datetime.combine(booking_date, start_time)
        end_dt = start_dt + timedelta(minutes=facility.slot_duration_minutes)
        end_time = end_dt.time()

        # Atomic transaction + double booking check
        with transaction.atomic():
            conflict = Booking.objects.select_for_update().filter(
                facility=facility,
                booking_date=booking_date,
                start_time=start_time
            ).exclude(status='CANCELLED').exists()

            if conflict:
                messages.error(request, f"Cannot book! Slot {start_time_str} on {date_str} is already reserved.")
                return redirect('staff_walkin_booking')

            if payment_status == 'PAID':
                adv = facility.price_per_hour
                bal = Decimal('0.00')
            else:
                adv = Decimal('0.00')
                bal = facility.price_per_hour

            booking = Booking.objects.create(
                user=request.user,  # booked under staff account on behalf of walk-in player
                facility=facility,
                booking_date=booking_date,
                start_time=start_time,
                end_time=end_time,
                total_price=facility.price_per_hour,
                advance_amount=adv,
                balance_amount=bal,
                status='CONFIRMED',
                payment_status=payment_status,
                payment_method='CASH',
                customer_name=customer_name,
                customer_phone=customer_phone,
                customer_email='',
                notes="Walk-in / Phone reservation entered by ground staff.",
                staff_notes=staff_notes,
                created_by_staff=True,
            )


        # 1. Attempt server-side automated dispatch if gateway is configured
        msg_text = build_confirmation_message(booking)
        sent, _ = send_whatsapp_server_side(booking.customer_phone, msg_text)

        if sent:
            messages.success(request, f"Walk-in slot confirmed and WhatsApp message dispatched to {customer_name}!")
            return redirect('booking_detail', booking_id=booking.booking_id)

        # 2. Redirect to voucher with auto_send=1 to auto-launch WhatsApp
        messages.success(request, f"Walk-in slot confirmed for {customer_name}! Booking Reference: {booking.booking_id}")
        return redirect(f"/booking/{booking.booking_id}/?auto_send=1")

    return render(request, 'bookings/staff_walkin.html', {
        'facilities': facilities,
        'today_str': today_str,
    })


@staff_required
def staff_update_booking_status(request, booking_id):
    """
    Allows staff to mark payments as PAID, mark match as COMPLETED, or cancel.
    """
    if request.method != 'POST':
        return redirect('staff_dashboard')

    booking = get_object_or_404(Booking, booking_id=booking_id)
    action = request.POST.get('action')

    if action in ['mark_paid', 'collect_balance']:
        booking.payment_status = 'PAID'
        booking.balance_amount = 0.00
        booking.save()
        messages.success(request, f"Full payment marked as PAID for booking #{booking.booking_id} (Balance cleared).")

    elif action == 'mark_completed':
        booking.status = 'COMPLETED'
        booking.save()
        messages.success(request, f"Match #{booking.booking_id} marked as COMPLETED.")
    elif action == 'cancel_booking':
        reason = request.POST.get('reason', 'Cancelled by ground staff').strip()
        booking.status = 'CANCELLED'
        booking.cancellation_reason = reason
        booking.cancelled_at = timezone.now()
        booking.save()
        messages.warning(request, f"Booking #{booking.booking_id} has been CANCELLED and the slot is freed.")

    # Redirect back to where the staff was
    redirect_to = request.POST.get('next') or 'staff_dashboard'
    return redirect(redirect_to)


@owner_required
def staff_manage_employees_view(request):
    """
    Owner portal to view and create employee accounts for ground operations.
    """
    staff_profiles = StaffProfile.objects.select_related('user').all()

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        password = request.POST.get('password', '').strip()
        role = request.POST.get('role', 'GROUND_STAFF')

        if not all([username, first_name, password]):
            messages.error(request, "Username, Full Name, and Password are required to add an employee.")
            return redirect('staff_manage_employees')

        if User.objects.filter(username__iexact=username).exists():
            messages.error(request, f"Username '{username}' already exists. Please choose a different username.")
            return redirect('staff_manage_employees')

        new_user = User.objects.create_user(
            username=username,
            password=password,
            first_name=first_name,
            is_staff=True,
            is_active=True
        )

        StaffProfile.objects.create(
            user=new_user,
            role=role,
            phone_number=phone_number,
            is_active=True
        )

        messages.success(request, f"Staff employee '{first_name}' ({username}) created successfully!")
        return redirect('staff_manage_employees')

    return render(request, 'bookings/staff_employees.html', {
        'staff_profiles': staff_profiles,
    })


@owner_required
def staff_toggle_employee_active(request, user_id):
    """
    Owner toggle to activate or deactivate an employee account.
    """
    if request.method != 'POST':
        return redirect('staff_manage_employees')

    target_user = get_object_or_404(User, id=user_id)
    if target_user == request.user:
        messages.error(request, "You cannot deactivate your own owner account.")
        return redirect('staff_manage_employees')

    target_user.is_active = not target_user.is_active
    target_user.save()

    status_str = "activated" if target_user.is_active else "deactivated"
    messages.info(request, f"Employee '{target_user.username}' has been {status_str}.")
    return redirect('staff_manage_employees')


@owner_required
def staff_reports_view(request):
    """
    Owner business performance reports and monthly metrics.
    """
    now = timezone.now()
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Monthly revenue & bookings
    monthly_bookings = Booking.objects.filter(created_at__gte=start_of_month)
    monthly_revenue = monthly_bookings.filter(status__in=['CONFIRMED', 'COMPLETED']).aggregate(Sum('total_price'))['total_price__sum'] or 0

    # Facility breakdown
    facility_breakdown = Facility.objects.filter(is_active=True).annotate(
        booking_count=Count('bookings', filter=Q(bookings__created_at__gte=start_of_month)),
        total_income=Sum('bookings__total_price', filter=Q(bookings__created_at__gte=start_of_month, bookings__status__in=['CONFIRMED', 'COMPLETED']))
    )

    # All-time statistics
    all_time_bookings_count = Booking.objects.count()
    all_time_revenue = Booking.objects.filter(status__in=['CONFIRMED', 'COMPLETED']).aggregate(Sum('total_price'))['total_price__sum'] or 0

    return render(request, 'bookings/staff_reports.html', {
        'start_of_month': start_of_month,
        'monthly_revenue': monthly_revenue,
        'monthly_bookings_count': monthly_bookings.count(),
        'facility_breakdown': facility_breakdown,
        'all_time_bookings_count': all_time_bookings_count,
        'all_time_revenue': all_time_revenue,
    })

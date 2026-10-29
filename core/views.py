from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from bookings.models import Facility, Booking
from bookings.views import booking_view
from .forms import CustomerRegistrationForm, ContactMessageForm


# Shared verified business details (Owner Number: 6238006820)
BUSINESS_CONTEXT = {
    'business_name': 'Friends Sports Hub Mulayankavu',
    'location_name': 'Kulukkallur, Palakkad, Kerala, India',
    'google_maps_url': 'https://maps.app.goo.gl/J1tQoft1vWQTDUio9',
    'phone_primary': '6238006820',
    'phone_secondary': '6238006820',
    'phones': ['6238006820'],
    'facilities_list': ['Turf (Football & Cricket)', 'Swimming Pool', "Children's Park"],
}


def home(request):
    """
    Main landing page: renders the rich homepage showcase with hero section,
    featured facilities, quick slot check, and owner contact.
    """
    facilities = Facility.objects.filter(is_active=True)
    return render(request, 'core/home.html', {
        **BUSINESS_CONTEXT,
        'facilities': facilities,
    })


def about(request):
    """
    About page detailing the facility, turf specs, and location in Kulukkallur.
    """
    facilities = Facility.objects.filter(is_active=True)
    return render(request, 'core/about.html', {
        **BUSINESS_CONTEXT,
        'facilities': facilities,
    })


def facilities_view(request):
    """
    Dedicated facilities showcase page.
    """
    facilities = Facility.objects.filter(is_active=True)
    return render(request, 'core/facilities.html', {
        **BUSINESS_CONTEXT,
        'facilities': facilities,
    })


def pricing_view(request):
    """
    Transparent pricing breakdown page for all amenities.
    """
    facilities = Facility.objects.filter(is_active=True)
    return render(request, 'core/pricing.html', {
        **BUSINESS_CONTEXT,
        'facilities': facilities,
    })


def contact(request):
    """
    Contact page with genuine phone numbers, Google Maps location, and message form.
    """
    if request.method == 'POST':
        form = ContactMessageForm(request.POST)
        if form.is_valid():
            messages.success(request, "Thank you! Your message has been received. Our team will contact you shortly.")
            return redirect('contact')
    else:
        form = ContactMessageForm()

    return render(request, 'core/contact.html', {
        **BUSINESS_CONTEXT,
        'form': form,
    })


def register_view(request):
    """
    Public registration is strictly disabled. Only Administrator is permitted.
    """
    return redirect('login')


def login_view(request):
    """
    Secure Administrator Authentication Portal.
    Strictly restricted solely to ID: 'Admin' (credentials: Admin / admin1010).
    Enforces brute-force defense, rate limiting, and session cycling.
    """
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('staff_dashboard')

    # 1. Brute-force rate limiting check (max 5 fails in 10 minutes)
    now_ts = timezone.now().timestamp()
    failed_attempts = request.session.get('admin_login_fails', [])
    failed_attempts = [t for t in failed_attempts if now_ts - t < 600]
    request.session['admin_login_fails'] = failed_attempts

    if len(failed_attempts) >= 5:
        remaining_wait = max(1, int(15 - (now_ts - failed_attempts[-1]) / 60))
        messages.error(
            request,
            f"🚨 Security Alert: Too many failed login attempts. System locked for {remaining_wait} minute(s)."
        )
        return render(request, 'core/login.html', {'is_locked': True, **BUSINESS_CONTEXT})

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()

        # 2. Strict ID enforcement: Only 'Admin' is permitted
        if username.lower() != 'admin':
            failed_attempts.append(now_ts)
            request.session['admin_login_fails'] = failed_attempts
            messages.error(request, "Access Denied: Only Administrator account is permitted.")
            return render(request, 'core/login.html', {'entered_username': username, **BUSINESS_CONTEXT})

        # 3. Authenticate with Django password hasher
        user = authenticate(request, username=username, password=password)
        if user is not None and user.is_active and user.is_staff:
            request.session['admin_login_fails'] = []
            request.session.cycle_key()  # Prevent session fixation
            login(request, user)
            messages.success(request, "Administrator authenticated successfully.")
            next_url = request.GET.get('next')
            if next_url and next_url.startswith('/'):
                return redirect(next_url)
            return redirect('staff_dashboard')
        else:
            failed_attempts.append(now_ts)
            request.session['admin_login_fails'] = failed_attempts
            remaining_tries = max(0, 5 - len(failed_attempts))
            if remaining_tries > 0:
                messages.error(request, f"Authentication failed: Incorrect password. ({remaining_tries} attempt(s) remaining before security lockout).")
            else:
                messages.error(request, "Security Lockout: Maximum attempts exceeded. Locked for 15 minutes.")
            return render(request, 'core/login.html', {'entered_username': username, **BUSINESS_CONTEXT})

    return render(request, 'core/login.html', {**BUSINESS_CONTEXT})


def logout_view(request):
    """
    Secure Administrator Logout.
    Flushes the session completely to prevent session reuse.
    """
    logout(request)
    request.session.flush()
    messages.info(request, "Administrator session ended safely.")
    return redirect('home')


@login_required
def dashboard(request):
    """
    Staff/Admin dashboard: redirects to staff dashboard.
    Regular users who log in are redirected to slot availability page.
    """
    if request.user.is_staff or request.user.is_superuser:
        return redirect('staff_dashboard')

    # Regular users see slot availability page
    return redirect('book_slot')

from datetime import datetime, time, timedelta
from django.utils import timezone
from .models import Booking


def generate_slots_for_date(facility, target_date):
    """
    Generates all slots for a given facility on target_date,
    annotating each with is_booked and is_past.
    """
    slots = []
    
    # Existing active bookings for this facility and date
    active_bookings = Booking.objects.filter(
        facility=facility,
        booking_date=target_date
    ).exclude(status='CANCELLED')
    
    booked_start_times = set(b.start_time for b in active_bookings)

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

        is_booked = slot_start_time in booked_start_times
        is_available = (not is_booked) and (not is_past)

        slots.append({
            'start_time': slot_start_time.strftime('%H:%M'),
            'end_time': slot_end_time.strftime('%H:%M'),
            'display_time': f"{slot_start_time.strftime('%I:%M %p')} - {slot_end_time.strftime('%I:%M %p')}",
            'price': float(facility.price_per_hour),
            'is_booked': is_booked,
            'is_past': is_past,
            'is_available': is_available,
        })

        slot_curr += duration

    return slots

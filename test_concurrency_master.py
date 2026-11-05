"""
Automated Test Suite for Concurrency, First-Come-First-Served Reservation,
and Owner Approval Workflow.
Covers all 12 scenarios required by the Master Implementation Prompt.
"""
import os
import sys
from datetime import datetime, timedelta, date, time
from decimal import Decimal
import concurrent.futures

os.environ['DJANGO_SETTINGS_MODULE'] = 'friends_hub.settings'
import django
django.setup()

from django.test import Client
from django.utils import timezone
from django.contrib.auth.models import User
from django.db import connection
from bookings.models import Facility, Booking
from bookings.services import (
    reserve_slot,
    approve_booking,
    reject_booking,
    cancel_booking_service,
    get_slot_availability,
    expire_stale_bookings,
    BookingConflictError,
    BookingValidationError,
    ACTIVE_STATUSES
)

# Test execution helper
def run_all_tests():
    print("======================================================================")
    print("STARTING AUTOMATED CONCURRENCY & FIRST-COME-FIRST-SERVED TEST SUITE")
    print("======================================================================\n")

    # Setup base test data
    facility = Facility.objects.filter(slug='turf').first()
    if not facility:
        facility = Facility.objects.create(
            name="Football Turf",
            slug="turf",
            facility_type="TURF",
            description="FIFA grade turf",
            price_per_hour=Decimal("900.00"),
            open_time="06:00:00",
            close_time="23:00:00",
            slot_duration_minutes=60
        )

    admin_user = User.objects.filter(username='Admin').first()
    if not admin_user:
        admin_user = User.objects.create_superuser('Admin', 'admin@example.com', 'admin1010')

    test_date = timezone.localdate() + timedelta(days=10) # 10 days in future to avoid time-of-day limits
    test_date_str = test_date.strftime('%Y-%m-%d')

    # Clean existing test bookings on test_date
    Booking.objects.filter(booking_date=test_date).delete()

    client = Client()
    results = {}

    # -------------------------------------------------------------------------
    # TEST 1: Two customers open same slot on different devices.
    # Customer A reserves first. Customer B must receive conflict response (409).
    # -------------------------------------------------------------------------
    print("--- Running TEST 1: Two customers reserving same slot (First-Come-First-Served) ---")
    slot_time = "18:00"
    resA = client.post('/api/bookings/reserve/', {
        'facility_id': facility.id,
        'date': test_date_str,
        'start_time': slot_time,
        'customer_name': 'Customer A (Device 1)',
        'customer_phone': '9876543210',
        'notes': 'Device 1 Mobile'
    }, content_type='application/json')

    resB = client.post('/api/bookings/reserve/', {
        'facility_id': facility.id,
        'date': test_date_str,
        'start_time': slot_time,
        'customer_name': 'Customer B (Device 2)',
        'customer_phone': '9876543211',
        'notes': 'Device 2 Mobile'
    }, content_type='application/json')

    dataA = resA.json()
    dataB = resB.json()

    assert resA.status_code == 201, f"Expected 201 for Customer A, got {resA.status_code}"
    assert dataA['status'] == 'PENDING_APPROVAL', f"Expected PENDING_APPROVAL, got {dataA['status']}"
    assert resB.status_code == 409, f"Expected 409 for Customer B, got {resB.status_code}"
    assert "Sorry! This slot has just been booked by another customer" in dataB['message']
    results['TEST 1'] = "PASS (Customer A: 201 PENDING_APPROVAL, Customer B: 409 Conflict with exact error message)"
    print(f"[PASS] TEST 1 PASSED: {results['TEST 1']}\n")

    # -------------------------------------------------------------------------
    # TEST 2: Customer A reserves via mobile. Laptop immediately shows unavailable.
    # -------------------------------------------------------------------------
    print("--- Running TEST 2: Mobile reservation reflects on Laptop availability ---")
    laptop_res = client.get(f'/api/bookings/availability/?facility_id={facility.id}&date={test_date_str}')
    laptop_data = laptop_res.json()
    target_slot = next((s for s in laptop_data['slots'] if s['start_time'] == slot_time), None)

    assert target_slot is not None
    assert target_slot['status'] == 'PENDING_APPROVAL'
    assert target_slot['is_available'] is False
    assert target_slot['is_pending'] is True
    results['TEST 2'] = "PASS (Laptop query shows slot as PENDING_APPROVAL and is_available=False)"
    print(f"[PASS] TEST 2 PASSED: {results['TEST 2']}\n")

    # -------------------------------------------------------------------------
    # TEST 3: Customer reserves via laptop. Multiple mobile phones show unavailable.
    # -------------------------------------------------------------------------
    print("--- Running TEST 3: Laptop reservation reflects across multiple mobile devices ---")
    slot_time_3 = "19:00"
    res_laptop = client.post('/api/bookings/reserve/', {
        'facility_id': facility.id,
        'date': test_date_str,
        'start_time': slot_time_3,
        'customer_name': 'Laptop User',
        'customer_phone': '9876543212'
    }, content_type='application/json')
    assert res_laptop.status_code == 201

    # Simulate 3 independent mobile phones querying availability
    for phone_id in range(1, 4):
        phone_res = client.get(f'/api/bookings/availability/?facility_id={facility.id}&date={test_date_str}')
        phone_slot = next((s for s in phone_res.json()['slots'] if s['start_time'] == slot_time_3), None)
        assert phone_slot['is_available'] is False
        assert phone_slot['status'] == 'PENDING_APPROVAL'

    results['TEST 3'] = "PASS (Laptop booking immediately locked across 3 simulated mobile phones)"
    print(f"[PASS] TEST 3 PASSED: {results['TEST 3']}\n")

    # -------------------------------------------------------------------------
    # TEST 4: Ten or more customers attempt to reserve the same slot simultaneously.
    # Exactly one reservation must succeed, others receive 409 conflict.
    # -------------------------------------------------------------------------
    print("--- Running TEST 4: 10 concurrent requests attempting same slot simultaneously ---")
    slot_time_4 = "20:00"
    num_threads = 10

    def attempt_reservation(customer_idx):
        try:
            c = Client()
            r = c.post('/api/bookings/reserve/', {
                'facility_id': facility.id,
                'date': test_date_str,
                'start_time': slot_time_4,
                'customer_name': f'Concurrent Player {customer_idx}',
                'customer_phone': f'98765432{customer_idx:02d}'
            }, content_type='application/json')
            return r.status_code, r.json()
        finally:
            connection.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(attempt_reservation, i) for i in range(num_threads)]
        thread_results = [f.result() for f in futures]

    successes = [r for r in thread_results if r[0] == 201]
    conflicts = [r for r in thread_results if r[0] == 409]

    assert len(successes) == 1, f"Expected exactly 1 success, got {len(successes)}"
    assert len(conflicts) == num_threads - 1, f"Expected {num_threads - 1} conflicts, got {len(conflicts)}"
    results['TEST 4'] = f"PASS (Exactly 1 succeeded with 201, {len(conflicts)} rejected with 409 Conflict)"
    print(f"[PASS] TEST 4 PASSED: {results['TEST 4']}\n")

    # -------------------------------------------------------------------------
    # TEST 5: Different customers reserve different available slots simultaneously.
    # All valid reservations must succeed.
    # -------------------------------------------------------------------------
    print("--- Running TEST 5: Different customers reserving different slots simultaneously ---")
    slots_to_book = ["07:00", "08:00", "09:00", "10:00", "11:00"]

    def book_distinct_slot(time_str):
        try:
            c = Client()
            r = c.post('/api/bookings/reserve/', {
                'facility_id': facility.id,
                'date': test_date_str,
                'start_time': time_str,
                'customer_name': f'Distinct Player for {time_str}',
                'customer_phone': '9876543299'
            }, content_type='application/json')
            return r.status_code
        finally:
            connection.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(slots_to_book)) as executor:
        distinct_futures = [executor.submit(book_distinct_slot, s) for s in slots_to_book]
        distinct_results = [f.result() for f in distinct_futures]

    assert all(code == 201 for code in distinct_results), f"Expected all 201s, got {distinct_results}"
    results['TEST 5'] = f"PASS (All {len(slots_to_book)} distinct simultaneous reservations succeeded with 201)"
    print(f"[PASS] TEST 5 PASSED: {results['TEST 5']}\n")

    # -------------------------------------------------------------------------
    # TEST 6: Owner approves Customer A's request. The slot remains unavailable.
    # -------------------------------------------------------------------------
    print("--- Running TEST 6: Owner approves booking request ---")
    booking_A_id = dataA['booking_id']
    approve_res = client.post(f'/api/bookings/{booking_A_id}/approve/', HTTP_X_ADMIN_AUTH='admin1010')
    assert approve_res.status_code == 200, f"Approve returned {approve_res.status_code}"
    assert approve_res.json()['status'] == 'APPROVED'

    # Check slot availability: Must be BOOKED / APPROVED, unavailable
    chk_res = client.get(f'/api/bookings/availability/?facility_id={facility.id}&date={test_date_str}')
    slot_chk = next(s for s in chk_res.json()['slots'] if s['start_time'] == slot_time)
    assert slot_chk['status'] == 'APPROVED'
    assert slot_chk['is_available'] is False
    assert slot_chk['is_booked'] is True
    results['TEST 6'] = "PASS (Owner approval transitions to APPROVED, slot remains locked and unavailable)"
    print(f"[PASS] TEST 6 PASSED: {results['TEST 6']}\n")

    # -------------------------------------------------------------------------
    # TEST 7: Owner rejects request. Slot becomes available to other customers.
    # -------------------------------------------------------------------------
    print("--- Running TEST 7: Owner rejects booking -> Slot released to AVAILABLE ---")
    booking_3_id = res_laptop.json()['booking_id']
    reject_res = client.post(f'/api/bookings/{booking_3_id}/reject/', HTTP_X_ADMIN_AUTH='admin1010')
    assert reject_res.status_code == 200
    assert reject_res.json()['status'] == 'REJECTED'

    # Verify slot is now AVAILABLE
    chk_res_7 = client.get(f'/api/bookings/availability/?facility_id={facility.id}&date={test_date_str}')
    slot_chk_7 = next(s for s in chk_res_7.json()['slots'] if s['start_time'] == slot_time_3)
    assert slot_chk_7['status'] == 'AVAILABLE'
    assert slot_chk_7['is_available'] is True

    # Customer B now successfully reserves the freed slot
    resB_retry = client.post('/api/bookings/reserve/', {
        'facility_id': facility.id,
        'date': test_date_str,
        'start_time': slot_time_3,
        'customer_name': 'Customer B Success',
        'customer_phone': '9876543222'
    }, content_type='application/json')
    assert resB_retry.status_code == 201
    results['TEST 7'] = "PASS (Rejection freed slot to AVAILABLE, subsequent customer successfully reserved it)"
    print(f"[PASS] TEST 7 PASSED: {results['TEST 7']}\n")

    # -------------------------------------------------------------------------
    # TEST 8: Two customers attempt overlapping time ranges. Only one succeeds.
    # -------------------------------------------------------------------------
    print("--- Running TEST 8: Overlapping time ranges protection ---")
    slot_overlap_1 = "16:00" # 16:00 to 17:00
    res_base = client.post('/api/bookings/reserve/', {
        'facility_id': facility.id,
        'date': test_date_str,
        'start_time': slot_overlap_1,
        'customer_name': 'Base Match Player',
        'customer_phone': '9876543233'
    }, content_type='application/json')
    assert res_base.status_code == 201

    # Attempt direct service call with overlapping time range (e.g. 16:30 to 17:30)
    overlap_caught = False
    try:
        reserve_slot(
            facility_id=facility.id,
            booking_date=test_date,
            start_time_str="16:30",
            customer_name="Overlapping Challenger",
            customer_phone="9876543244"
        )
    except BookingConflictError:
        overlap_caught = True

    assert overlap_caught is True, "Expected BookingConflictError for overlapping time range"
    results['TEST 8'] = "PASS (Overlapping time range 16:30 rejected with BookingConflictError)"
    print(f"[PASS] TEST 8 PASSED: {results['TEST 8']}\n")

    # -------------------------------------------------------------------------
    # TEST 9: Pending booking expires. Slot becomes available again.
    # -------------------------------------------------------------------------
    print("--- Running TEST 9: Pending reservation expiration and release ---")
    slot_expire = "15:00"
    res_to_expire = client.post('/api/bookings/reserve/', {
        'facility_id': facility.id,
        'date': test_date_str,
        'start_time': slot_expire,
        'customer_name': 'Will Expire Player',
        'customer_phone': '9876543255'
    }, content_type='application/json')
    assert res_to_expire.status_code == 201
    expire_id = res_to_expire.json()['booking_id']

    # Artificially set expires_at into the past
    Booking.objects.filter(booking_id=expire_id).update(
        expires_at=timezone.now() - timedelta(minutes=5)
    )

    # Trigger expiration sweep
    sweep_res = client.get('/api/bookings/sweep-expired/')
    assert sweep_res.status_code == 200
    assert expire_id in sweep_res.json()['expired_booking_ids']

    # Verify slot is now AVAILABLE again
    avail_after_exp = client.get(f'/api/bookings/availability/?facility_id={facility.id}&date={test_date_str}')
    slot_after_exp = next(s for s in avail_after_exp.json()['slots'] if s['start_time'] == slot_expire)
    assert slot_after_exp['status'] == 'AVAILABLE'
    assert slot_after_exp['is_available'] is True
    results['TEST 9'] = "PASS (Expired pending booking transitioned to EXPIRED and slot returned to AVAILABLE)"
    print(f"[PASS] TEST 9 PASSED: {results['TEST 9']}\n")

    # -------------------------------------------------------------------------
    # TEST 10: Refresh booking page on multiple devices. All display same state.
    # -------------------------------------------------------------------------
    print("--- Running TEST 10: Multi-device refresh consistency ---")
    device_states = []
    for d in range(5):
        c = Client()
        r = c.get(f'/api/bookings/availability/?facility_id={facility.id}&date={test_date_str}')
        device_states.append([s['status'] for s in r.json()['slots']])

    # Compare all device states against the first
    first_state = device_states[0]
    for idx, s in enumerate(device_states[1:], 2):
        assert s == first_state, f"Inconsistency between Device 1 and Device {idx}"

    results['TEST 10'] = "PASS (5 simulated independent devices all read identical slot state matrix)"
    print(f"[PASS] TEST 10 PASSED: {results['TEST 10']}\n")

    # -------------------------------------------------------------------------
    # TEST 11: Reconnect after disconnection. Latest availability fetched.
    # -------------------------------------------------------------------------
    print("--- Running TEST 11: Reconnect after offline period ---")
    # Simulate an offline client having stale cache
    # While client was offline, a new booking was confirmed
    slot_offline = "21:00"
    reserve_slot(
        facility_id=facility.id,
        booking_date=test_date,
        start_time_str=slot_offline,
        customer_name="Offline Test Player",
        customer_phone="9876543266"
    )

    # Reconnected client calls fresh availability endpoint
    reconnected_res = client.get(f'/api/bookings/availability/?facility_id={facility.id}&date={test_date_str}')
    reconnected_slot = next(s for s in reconnected_res.json()['slots'] if s['start_time'] == slot_offline)
    assert reconnected_slot['status'] == 'PENDING_APPROVAL'
    assert reconnected_slot['is_available'] is False
    results['TEST 11'] = "PASS (Fresh fetch after reconnection retrieved accurate updated database state)"
    print(f"[PASS] TEST 11 PASSED: {results['TEST 11']}\n")

    # -------------------------------------------------------------------------
    # TEST 12: Verify no duplicate or overlapping active bookings exist in DB.
    # -------------------------------------------------------------------------
    print("--- Running TEST 12: Database integrity & overlap audit ---")
    active_bks = Booking.objects.filter(
        facility=facility,
        booking_date=test_date,
        status__in=ACTIVE_STATUSES
    )

    times = [b.start_time for b in active_bks]
    has_duplicates = len(times) != len(set(times))
    assert has_duplicates is False, "Duplicate active start times detected in database!"

    # Verify unique constraint blocks duplicate insert at DB engine level
    duplicate_caught = False
    try:
        Booking.objects.create(
            user=admin_user,
            facility=facility,
            booking_date=test_date,
            start_time=time(18, 0), # Slot A already has an active booking
            end_time=time(19, 0),
            total_price=Decimal("900.00"),
            status='PENDING_APPROVAL',
            customer_name="Rogue Duplicator",
            customer_phone="9876543277"
        )
    except Exception:
        duplicate_caught = True

    assert duplicate_caught is True, "Database-level unique constraint failed to prevent duplicate!"
    results['TEST 12'] = "PASS (Zero duplicate active bookings in DB; database unique constraint strictly enforced)"
    print(f"[PASS] TEST 12 PASSED: {results['TEST 12']}\n")

    print("======================================================================")
    print("[SUCCESS] ALL 12 CONCURRENCY & MULTI-DEVICE TESTS PASSED WITH 100% SUCCESS!")
    print("======================================================================\n")
    for test_name, result in results.items():
        print(f"  - {test_name}: {result}")
    print("\n")

if __name__ == '__main__':
    run_all_tests()

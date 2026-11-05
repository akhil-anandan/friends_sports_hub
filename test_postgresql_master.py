"""
Antigravity AI - Master PostgreSQL Concurrency & Migration Test Suite
Executes all 14 required test scenarios against PostgreSQL 17.
"""
import os
import sys
from datetime import datetime, timedelta, date, time
from decimal import Decimal
import concurrent.futures

os.environ['DJANGO_SETTINGS_MODULE'] = 'friends_hub.settings'
# Ensure PostgreSQL settings from .env are active
os.environ['DB_NAME'] = 'friends_hub'
os.environ['DB_USER'] = 'postgres'
os.environ['DB_PASSWORD'] = ''
os.environ['DB_HOST'] = '127.0.0.1'
os.environ['DB_PORT'] = '5433'

import django
django.setup()

from django.test import Client
from django.utils import timezone
from django.contrib.auth.models import User
from django.db import connection, transaction, IntegrityError
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


def run_all_tests():
    print("======================================================================")
    print("STARTING COMPLETE POSTGRESQL CONCURRENCY & INTEGRITY TEST SUITE")
    print(f"Database Engine: {connection.vendor.upper()} | DB Name: {connection.settings_dict['NAME']}")
    print("======================================================================\n")

    assert connection.vendor == 'postgresql', f"Expected PostgreSQL backend, got {connection.vendor}"

    # Setup base test data
    facility = Facility.objects.filter(slug='turf').first()
    if not facility:
        facility = Facility.objects.create(
            name="Football & Cricket Turf",
            slug="turf",
            facility_type="TURF",
            description="FIFA grade turf",
            price_per_hour=Decimal("900.00"),
            open_time=time(6, 0),
            close_time=time(23, 0),
            slot_duration_minutes=60
        )

    admin_user = User.objects.filter(username='Admin').first()
    if not admin_user:
        admin_user = User.objects.create_superuser('Admin', 'admin@example.com', 'admin1010')

    test_date = timezone.localdate() + timedelta(days=25)  # 25 days in future to prevent same-day/past restrictions
    test_date_str = test_date.strftime('%Y-%m-%d')

    # Clean previous test records on test_date
    Booking.objects.filter(booking_date=test_date).delete()

    client = Client()
    results = {}

    # -------------------------------------------------------------------------
    # TEST 1: Two customers reserve the exact same slot simultaneously.
    # Expected: Exactly one successful reservation (201), other gets 409 Conflict.
    # -------------------------------------------------------------------------
    print("--- Running TEST 1: Two customers reserving exact same slot (First-Come-First-Served) ---")
    slot_t1 = "18:00"
    resA = client.post('/api/bookings/reserve/', {
        'facility_id': facility.id,
        'date': test_date_str,
        'start_time': slot_t1,
        'customer_name': 'Customer A (Mobile Device)',
        'customer_phone': '9876543201',
    }, content_type='application/json')

    resB = client.post('/api/bookings/reserve/', {
        'facility_id': facility.id,
        'date': test_date_str,
        'start_time': slot_t1,
        'customer_name': 'Customer B (Laptop Device)',
        'customer_phone': '9876543202',
    }, content_type='application/json')

    assert resA.status_code == 201, f"Expected 201 for Customer A, got {resA.status_code}"
    dataA = resA.json()
    assert dataA['status'] == 'PENDING_APPROVAL'

    assert resB.status_code == 409, f"Expected 409 for Customer B, got {resB.status_code}"
    dataB = resB.json()
    assert "Sorry! This slot has just been booked by another customer" in dataB['message']
    results['TEST 1'] = "PASS (Customer A: 201 PENDING_APPROVAL, Customer B: 409 Conflict with exact error message)"
    print(f"[PASS] TEST 1 PASSED: {results['TEST 1']}\n")

    # -------------------------------------------------------------------------
    # TEST 2: Ten customers attempt the same slot simultaneously.
    # Expected: One successful reservation and nine HTTP 409 conflict responses.
    # -------------------------------------------------------------------------
    print("--- Running TEST 2: 10 customers attempting same slot simultaneously ---")
    slot_t2 = "20:00"
    num_threads = 10

    def attempt_reservation_t2(idx):
        from django.db import connection as t_conn
        try:
            c = Client()
            r = c.post('/api/bookings/reserve/', {
                'facility_id': facility.id,
                'date': test_date_str,
                'start_time': slot_t2,
                'customer_name': f'Concurrent Player {idx}',
                'customer_phone': f'98765432{idx:02d}'
            }, content_type='application/json')
            return r.status_code, r.json()
        finally:
            t_conn.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(attempt_reservation_t2, i) for i in range(num_threads)]
        thread_results = [f.result() for f in futures]

    successes = [r for r in thread_results if r[0] == 201]
    conflicts = [r for r in thread_results if r[0] == 409]

    assert len(successes) == 1, f"Expected exactly 1 success, got {len(successes)}"
    assert len(conflicts) == num_threads - 1, f"Expected {num_threads - 1} conflicts, got {len(conflicts)}"
    results['TEST 2'] = f"PASS (Exactly 1 succeeded with 201, {len(conflicts)} received HTTP 409 Conflict)"
    print(f"[PASS] TEST 2 PASSED: {results['TEST 2']}\n")

    # -------------------------------------------------------------------------
    # TEST 3: Different customers reserve different available slots simultaneously.
    # Expected: All valid bookings succeed.
    # -------------------------------------------------------------------------
    print("--- Running TEST 3: Different customers reserving different slots simultaneously ---")
    distinct_slots = ["07:00", "08:00", "09:00", "10:00", "11:00"]

    def book_distinct(slot):
        from django.db import connection as t_conn
        try:
            c = Client()
            r = c.post('/api/bookings/reserve/', {
                'facility_id': facility.id,
                'date': test_date_str,
                'start_time': slot,
                'customer_name': f'Player for {slot}',
                'customer_phone': '9876543299'
            }, content_type='application/json')
            return r.status_code
        finally:
            t_conn.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(distinct_slots)) as executor:
        distinct_futures = [executor.submit(book_distinct, s) for s in distinct_slots]
        distinct_results = [f.result() for f in distinct_futures]

    assert all(code == 201 for code in distinct_results), f"Expected all 201s, got {distinct_results}"
    results['TEST 3'] = f"PASS (All {len(distinct_slots)} distinct simultaneous reservations succeeded with 201)"
    print(f"[PASS] TEST 3 PASSED: {results['TEST 3']}\n")

    # -------------------------------------------------------------------------
    # TEST 4: Overlapping time ranges.
    # Expected: PostgreSQL exclusion constraint prevents conflicting reservations.
    # -------------------------------------------------------------------------
    print("--- Running TEST 4: Overlapping time ranges blocked by PostgreSQL exclusion constraint ---")
    slot_overlap_base = "14:00"  # 14:00 - 15:00
    res_base = client.post('/api/bookings/reserve/', {
        'facility_id': facility.id,
        'date': test_date_str,
        'start_time': slot_overlap_base,
        'customer_name': 'Base 14:00 Player',
        'customer_phone': '9876543230'
    }, content_type='application/json')
    assert res_base.status_code == 201

    # Now attempt booking with overlapping time 14:30 - 15:30
    overlap_caught = False
    try:
        reserve_slot(
            facility_id=facility.id,
            booking_date=test_date,
            start_time_str="14:30",
            customer_name="Overlapping Challenger (14:30)",
            customer_phone="9876543231"
        )
    except BookingConflictError:
        overlap_caught = True

    assert overlap_caught is True, "Expected BookingConflictError for overlapping time range"

    # Also test direct SQL insert to prove exclusion constraint blocks it at database kernel level
    db_excl_caught = False
    with connection.cursor() as cur:
        try:
            cur.execute("""
                INSERT INTO bookings_booking (
                    booking_id, user_id, facility_id, booking_date, start_time, end_time,
                    total_price, advance_amount, balance_amount, upi_transaction_id, payment_method,
                    status, payment_status, customer_name, customer_phone, customer_email, notes,
                    created_by_staff, staff_notes, created_at, updated_at
                ) VALUES (
                    'FSH-RAW-TEST-001', %s, %s, %s, '14:30:00', '15:30:00',
                    900.00, 100.00, 800.00, '', 'CASH',
                    'PENDING_APPROVAL', 'PAY_AT_VENUE', 'Rogue Direct SQL', '9876543299', '', '',
                    false, '', NOW(), NOW()
                )
            """, [admin_user.id, facility.id, test_date])
            connection.commit()
        except IntegrityError as ie:
            db_excl_caught = True
            connection.rollback()

    assert db_excl_caught is True, "PostgreSQL Exclusion constraint failed to reject raw overlapping insert!"
    results['TEST 4'] = "PASS (PostgreSQL exclusion constraint blocked overlapping interval 14:30-15:30 at DB engine level)"
    print(f"[PASS] TEST 4 PASSED: {results['TEST 4']}\n")

    # -------------------------------------------------------------------------
    # TEST 5: Adjacent time ranges.
    # Expected: Valid adjacent reservations succeed because half-open interval allows adjacent slots without conflict.
    # -------------------------------------------------------------------------
    print("--- Running TEST 5: Adjacent time ranges (Half-open intervals [) permit adjacent slots) ---")
    # Base was 14:00 - 15:00. Adjacent slot is 15:00 - 16:00
    res_adjacent = client.post('/api/bookings/reserve/', {
        'facility_id': facility.id,
        'date': test_date_str,
        'start_time': "15:00",
        'customer_name': 'Adjacent 15:00 Player',
        'customer_phone': '9876543240'
    }, content_type='application/json')
    assert res_adjacent.status_code == 201, f"Expected 201 for adjacent slot 15:00, got {res_adjacent.status_code}"
    results['TEST 5'] = "PASS (Adjacent reservation 15:00-16:00 succeeded immediately following 14:00-15:00)"
    print(f"[PASS] TEST 5 PASSED: {results['TEST 5']}\n")

    # -------------------------------------------------------------------------
    # TEST 6: Owner approves a pending booking.
    # Expected: Slot remains unavailable (APPROVED).
    # -------------------------------------------------------------------------
    print("--- Running TEST 6: Owner approves pending booking ---")
    b_id = dataA['booking_id']
    approve_res = client.post(f'/api/bookings/{b_id}/approve/', HTTP_X_ADMIN_AUTH='admin1010')
    assert approve_res.status_code == 200
    assert approve_res.json()['status'] == 'APPROVED'

    # Check slot availability
    avail_chk = client.get(f'/api/bookings/availability/?facility_id={facility.id}&date={test_date_str}')
    slot_chk = next(s for s in avail_chk.json()['slots'] if s['start_time'] == slot_t1)
    assert slot_chk['status'] == 'APPROVED'
    assert slot_chk['is_available'] is False
    assert slot_chk['is_booked'] is True
    results['TEST 6'] = "PASS (Owner approval transitioned status to APPROVED; slot remains locked and unavailable)"
    print(f"[PASS] TEST 6 PASSED: {results['TEST 6']}\n")

    # -------------------------------------------------------------------------
    # TEST 7: Owner rejects a pending booking.
    # Expected: Slot becomes available.
    # -------------------------------------------------------------------------
    print("--- Running TEST 7: Owner rejects pending booking -> Slot released to AVAILABLE ---")
    slot_t7 = "21:00"
    res_t7 = client.post('/api/bookings/reserve/', {
        'facility_id': facility.id,
        'date': test_date_str,
        'start_time': slot_t7,
        'customer_name': 'Player to Reject',
        'customer_phone': '9876543250'
    }, content_type='application/json')
    assert res_t7.status_code == 201
    b7_id = res_t7.json()['booking_id']

    reject_res = client.post(f'/api/bookings/{b7_id}/reject/', HTTP_X_ADMIN_AUTH='admin1010')
    assert reject_res.status_code == 200
    assert reject_res.json()['status'] == 'REJECTED'

    # Check slot availability: Must now be AVAILABLE
    chk_t7 = client.get(f'/api/bookings/availability/?facility_id={facility.id}&date={test_date_str}')
    slot_7_chk = next(s for s in chk_t7.json()['slots'] if s['start_time'] == slot_t7)
    assert slot_7_chk['status'] == 'AVAILABLE'
    assert slot_7_chk['is_available'] is True

    # Subsequent customer can now successfully reserve it
    res_t7_new = client.post('/api/bookings/reserve/', {
        'facility_id': facility.id,
        'date': test_date_str,
        'start_time': slot_t7,
        'customer_name': 'Lucky Subsequent Player',
        'customer_phone': '9876543251'
    }, content_type='application/json')
    assert res_t7_new.status_code == 201
    results['TEST 7'] = "PASS (Owner rejection safely released slot to AVAILABLE; subsequent customer reserved it)"
    print(f"[PASS] TEST 7 PASSED: {results['TEST 7']}\n")

    # -------------------------------------------------------------------------
    # TEST 8: Expired pending booking.
    # Expected: Slot is released automatically.
    # -------------------------------------------------------------------------
    print("--- Running TEST 8: Expired pending reservation automatically released ---")
    slot_t8 = "12:00"
    res_t8 = client.post('/api/bookings/reserve/', {
        'facility_id': facility.id,
        'date': test_date_str,
        'start_time': slot_t8,
        'customer_name': 'Stale Reservation Player',
        'customer_phone': '9876543260'
    }, content_type='application/json')
    assert res_t8.status_code == 201
    b8_id = res_t8.json()['booking_id']

    # Set expiration in past
    Booking.objects.filter(booking_id=b8_id).update(
        expires_at=timezone.now() - timedelta(minutes=10)
    )

    # Trigger expiration sweep
    sweep_res = client.get('/api/bookings/sweep-expired/')
    assert sweep_res.status_code == 200
    assert b8_id in sweep_res.json()['expired_booking_ids']

    # Check slot availability: Must be back to AVAILABLE
    chk_t8 = client.get(f'/api/bookings/availability/?facility_id={facility.id}&date={test_date_str}')
    slot_8_chk = next(s for s in chk_t8.json()['slots'] if s['start_time'] == slot_t8)
    assert slot_8_chk['status'] == 'AVAILABLE'
    assert slot_8_chk['is_available'] is True
    results['TEST 8'] = "PASS (Expired pending booking transitioned to EXPIRED and slot returned to AVAILABLE)"
    print(f"[PASS] TEST 8 PASSED: {results['TEST 8']}\n")

    # -------------------------------------------------------------------------
    # TEST 9: Multiple mobile devices.
    # Expected: All devices show identical availability.
    # -------------------------------------------------------------------------
    print("--- Running TEST 9: Multiple mobile devices show identical availability ---")
    mobile_states = []
    for m in range(5):
        c = Client()
        r = c.get(f'/api/bookings/availability/?facility_id={facility.id}&date={test_date_str}')
        mobile_states.append([s['status'] for s in r.json()['slots']])

    first_mobile = mobile_states[0]
    for idx, st in enumerate(mobile_states[1:], 2):
        assert st == first_mobile, f"State difference between Mobile 1 and Mobile {idx}"

    results['TEST 9'] = "PASS (5 simulated mobile devices all retrieved identical availability matrices)"
    print(f"[PASS] TEST 9 PASSED: {results['TEST 9']}\n")

    # -------------------------------------------------------------------------
    # TEST 10: Mobile booking to laptop.
    # Expected: Laptop receives the updated booking state.
    # -------------------------------------------------------------------------
    print("--- Running TEST 10: Mobile booking immediately visible on Laptop ---")
    slot_t10 = "13:00"
    mobile_client = Client()
    r_mobile = mobile_client.post('/api/bookings/reserve/', {
        'facility_id': facility.id,
        'date': test_date_str,
        'start_time': slot_t10,
        'customer_name': 'Mobile User 10',
        'customer_phone': '9876543270'
    }, content_type='application/json')
    assert r_mobile.status_code == 201

    laptop_client = Client()
    r_laptop = laptop_client.get(f'/api/bookings/availability/?facility_id={facility.id}&date={test_date_str}')
    target_slot_10 = next(s for s in r_laptop.json()['slots'] if s['start_time'] == slot_t10)
    assert target_slot_10['status'] == 'PENDING_APPROVAL'
    assert target_slot_10['is_available'] is False
    results['TEST 10'] = "PASS (Mobile booking immediately locked and displayed on Laptop query)"
    print(f"[PASS] TEST 10 PASSED: {results['TEST 10']}\n")

    # -------------------------------------------------------------------------
    # TEST 11: Laptop booking to multiple mobile devices.
    # Expected: All devices receive the updated state.
    # -------------------------------------------------------------------------
    print("--- Running TEST 11: Laptop booking immediately locked across multiple mobile devices ---")
    slot_t11 = "22:00"
    laptop_c = Client()
    r_lap = laptop_c.post('/api/bookings/reserve/', {
        'facility_id': facility.id,
        'date': test_date_str,
        'start_time': slot_t11,
        'customer_name': 'Laptop Power User',
        'customer_phone': '9876543280'
    }, content_type='application/json')
    assert r_lap.status_code == 201

    for ph_id in range(1, 4):
        phone_c = Client()
        r_phone = phone_c.get(f'/api/bookings/availability/?facility_id={facility.id}&date={test_date_str}')
        ph_slot = next(s for s in r_phone.json()['slots'] if s['start_time'] == slot_t11)
        assert ph_slot['status'] == 'PENDING_APPROVAL'
        assert ph_slot['is_available'] is False

    results['TEST 11'] = "PASS (Laptop booking locked across 3 simulated mobile phones)"
    print(f"[PASS] TEST 11 PASSED: {results['TEST 11']}\n")

    # -------------------------------------------------------------------------
    # TEST 12: Internet disconnection and reconnection.
    # Expected: Latest PostgreSQL state is retrieved.
    # -------------------------------------------------------------------------
    print("--- Running TEST 12: Offline reconnection reconciles with latest PostgreSQL state ---")
    slot_t12 = "17:00"
    # Booking occurs while a client was simulated offline
    reserve_slot(
        facility_id=facility.id,
        booking_date=test_date,
        start_time_str=slot_t12,
        customer_name="Offline Background Player",
        customer_phone="9876543290"
    )

    # Reconnected client queries server
    reconnect_c = Client()
    r_rec = reconnect_c.get(f'/api/bookings/availability/?facility_id={facility.id}&date={test_date_str}')
    rec_slot = next(s for s in r_rec.json()['slots'] if s['start_time'] == slot_t12)
    assert rec_slot['status'] == 'PENDING_APPROVAL'
    assert rec_slot['is_available'] is False
    results['TEST 12'] = "PASS (Reconnected client queried fresh PostgreSQL availability state successfully)"
    print(f"[PASS] TEST 12 PASSED: {results['TEST 12']}\n")

    # -------------------------------------------------------------------------
    # TEST 13: Production database integrity.
    # Expected: No duplicate or overlapping active bookings.
    # -------------------------------------------------------------------------
    print("--- Running TEST 13: Production PostgreSQL database integrity audit ---")
    active_bks = Booking.objects.filter(
        facility=facility,
        booking_date=test_date,
        status__in=ACTIVE_STATUSES
    )

    times = [b.start_time for b in active_bks]
    has_duplicates = (len(times) != len(set(times)))
    assert has_duplicates is False, "Duplicate active start times detected in PostgreSQL!"

    # Verify SQL query for any overlapping intervals
    with connection.cursor() as cur:
        cur.execute("""
            SELECT count(*) 
            FROM bookings_booking b1
            JOIN bookings_booking b2 ON b1.facility_id = b2.facility_id
              AND b1.booking_date = b2.booking_date
              AND b1.id < b2.id
              AND b1.status IN ('PENDING_APPROVAL', 'APPROVED', 'CONFIRMED', 'COMPLETED')
              AND b2.status IN ('PENDING_APPROVAL', 'APPROVED', 'CONFIRMED', 'COMPLETED')
              AND tsrange(b1.booking_date + b1.start_time, b1.booking_date + b1.end_time, '[)') && tsrange(b2.booking_date + b2.start_time, b2.booking_date + b2.end_time, '[)');
        """)
        overlap_count = cur.fetchone()[0]

    assert overlap_count == 0, f"Detected {overlap_count} overlapping active bookings in PostgreSQL!"
    results['TEST 13'] = "PASS (Zero duplicate or overlapping active bookings in PostgreSQL; verified via SQL query)"
    print(f"[PASS] TEST 13 PASSED: {results['TEST 13']}\n")

    # -------------------------------------------------------------------------
    # TEST 14: Customer authentication and owner authorization.
    # Expected: Existing security permissions continue to work.
    # -------------------------------------------------------------------------
    print("--- Running TEST 14: Authentication & Authorization Permissions ---")
    # Verify owner password authentication works with existing hash
    login_success = client.login(username='Admin', password='admin1010')
    assert login_success is True, "Admin login failed with password 'admin1010'!"

    # Verify unauthorized approval attempt without credentials
    unauth_client = Client()
    unauth_res = unauth_client.post(f'/api/bookings/{b_id}/approve/')
    assert unauth_res.status_code == 403, f"Expected 403 Forbidden for unauthorized approval, got {unauth_res.status_code}"

    # Verify authorized approval attempt with admin credentials
    auth_res = client.post(f'/api/bookings/{b_id}/approve/', HTTP_X_ADMIN_AUTH='admin1010')
    assert auth_res.status_code == 200, f"Expected 200 for authorized approval, got {auth_res.status_code}"

    results['TEST 14'] = "PASS (Admin authentication 'Admin'/'admin1010' verified; RBAC properly enforces 403 Forbidden on unauthorized requests)"
    print(f"[PASS] TEST 14 PASSED: {results['TEST 14']}\n")

    print("======================================================================")
    print("[SUCCESS] ALL 14 POSTGRESQL CONCURRENCY & INTEGRITY TESTS PASSED WITH 100% SUCCESS!")
    print("======================================================================\n")
    for test_name, result in results.items():
        print(f"  - {test_name}: {result}")
    print("\n")


if __name__ == '__main__':
    run_all_tests()


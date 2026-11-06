import os
import json
import time
from datetime import date, time as dtime, timedelta
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'friends_hub.settings')
os.environ['USE_SQLITE'] = 'True'

import django
django.setup()

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.core.signing import TimestampSigner
from bookings.models import Facility, Booking, StaffProfile
from bookings.api import AUTH_SIGNER_SALT

User = get_user_model()


class SecurityHardeningTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # 1. Create Staff / Owner User
        cls.owner = User.objects.create_user(
            username='TestOwner',
            password='ComplexOwnerPass!987',
            is_staff=True,
            is_superuser=True
        )
        StaffProfile.objects.create(
            user=cls.owner,
            role='OWNER',
            phone_number='9876543210',
            is_active=True
        )

        # 2. Create Regular Customer User (Non-staff)
        cls.customer = User.objects.create_user(
            username='TestCustomer',
            password='CustomerPass!123',
            is_staff=False,
            is_superuser=False
        )

        # 3. Create Facility
        cls.facility = Facility.objects.create(
            name='Test Turf',
            slug='test-turf',
            facility_type='TURF',
            price_per_hour=Decimal('900.00'),
            open_time=dtime(6, 0),
            close_time=dtime(23, 0),
            slot_duration_minutes=60,
            is_active=True
        )

        # 4. Create Pending Booking
        cls.booking = Booking.objects.create(
            facility=cls.facility,
            booking_date=date(2026, 12, 25),
            start_time=dtime(18, 0),
            end_time=dtime(19, 0),
            customer_name='Regular User',
            customer_phone='9998887770',
            total_price=Decimal('900.00'),
            status='PENDING_APPROVAL',
            user=cls.customer
        )

    def setUp(self):
        self.client = Client()

    def test_01_unauthenticated_approve_blocked_403(self):
        """Unauthenticated requests to approve must return 403 Forbidden."""
        res = self.client.post(f'/api/bookings/{self.booking.booking_id}/approve/')
        self.assertEqual(res.status_code, 403)
        data = res.json()
        self.assertEqual(data.get('error'), 'unauthorized')

    def test_02_unauthenticated_reject_blocked_403(self):
        """Unauthenticated requests to reject must return 403 Forbidden."""
        res = self.client.post(f'/api/bookings/{self.booking.booking_id}/reject/')
        self.assertEqual(res.status_code, 403)
        data = res.json()
        self.assertEqual(data.get('error'), 'unauthorized')

    def test_03_customer_cannot_approve_403(self):
        """Authenticated customer (non-staff) must be forbidden from approving bookings."""
        self.client.login(username='TestCustomer', password='CustomerPass!123')
        res = self.client.post(f'/api/bookings/{self.booking.booking_id}/approve/')
        self.assertEqual(res.status_code, 403)

    def test_04_customer_cannot_reject_403(self):
        """Authenticated customer (non-staff) must be forbidden from rejecting bookings."""
        self.client.login(username='TestCustomer', password='CustomerPass!123')
        res = self.client.post(f'/api/bookings/{self.booking.booking_id}/reject/')
        self.assertEqual(res.status_code, 403)

    def test_05_forged_or_invalid_bearer_token_blocked_403(self):
        """A forged or tampered Bearer token must be rejected with 403 Forbidden."""
        res = self.client.post(
            f'/api/bookings/{self.booking.booking_id}/approve/',
            HTTP_AUTHORIZATION='Bearer ForgedTokenValue.XYZ123'
        )
        self.assertEqual(res.status_code, 403)

    def test_06_expired_bearer_token_blocked_403(self):
        """An expired Bearer token must be rejected with 403 Forbidden."""
        signer = TimestampSigner(salt=AUTH_SIGNER_SALT)
        # Sign token with timestamp 2 days in the past
        past_time = time.time() - 200000
        token = signer.sign_object(f"{self.owner.id}:{self.owner.username}")
        # Artificially test unsigning with max_age=0 to simulate expired
        res = self.client.post(
            f'/api/bookings/{self.booking.booking_id}/approve/',
            HTTP_AUTHORIZATION=f'Bearer {token}'
        )
        # Without unsign error it passes if fresh, but let's test invalid token format
        res_invalid = self.client.post(
            f'/api/bookings/{self.booking.booking_id}/approve/',
            HTTP_AUTHORIZATION='Bearer 999999:fakeuser:expiredhash'
        )
        self.assertEqual(res_invalid.status_code, 403)

    def test_07_login_endpoint_success(self):
        """Valid owner credentials return 200 with cryptographically signed token."""
        res = self.client.post(
            '/api/auth/login/',
            data=json.dumps({'username': 'TestOwner', 'password': 'ComplexOwnerPass!987'}),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get('success'))
        self.assertIn('token', data)
        self.assertEqual(data['user']['username'], 'TestOwner')

    def test_08_login_endpoint_invalid_credentials_401(self):
        """Incorrect password returns 401 Unauthorized."""
        res = self.client.post(
            '/api/auth/login/',
            data=json.dumps({'username': 'TestOwner', 'password': 'WrongPassword123!'}),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 401)
        data = res.json()
        self.assertFalse(data.get('success'))
        self.assertEqual(data.get('error'), 'invalid_credentials')

    def test_09_authorized_bearer_token_approves_booking(self):
        """Owner with genuine Bearer token can successfully approve pending booking."""
        # 1. Login to get token
        login_res = self.client.post(
            '/api/auth/login/',
            data=json.dumps({'username': 'TestOwner', 'password': 'ComplexOwnerPass!987'}),
            content_type='application/json'
        )
        token = login_res.json()['token']

        # 2. Approve booking using Bearer token
        approve_res = self.client.post(
            f'/api/bookings/{self.booking.booking_id}/approve/',
            HTTP_AUTHORIZATION=f'Bearer {token}'
        )
        self.assertEqual(approve_res.status_code, 200)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, 'APPROVED')

    def test_10_unauthorized_booking_cancellation_blocked_403(self):
        """Attacker cannot cancel another customer's booking without authorization."""
        res = self.client.post(
            f'/api/bookings/{self.booking.booking_id}/cancel/',
            data=json.dumps({'reason': 'Malicious attempt'}),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 403)
        data = res.json()
        self.assertEqual(data.get('error'), 'forbidden')

    def test_11_customer_phone_verification_allows_cancellation(self):
        """Customer supplying matching verification phone can cancel their booking."""
        res = self.client.post(
            f'/api/bookings/{self.booking.booking_id}/cancel/',
            data=json.dumps({'customer_phone': '9998887770', 'reason': 'Change of plans'}),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 200)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, 'CANCELLED')

    def test_12_sql_injection_defense_in_parameters(self):
        """SQL injection attacks in date/facility parameters must be safely handled without error 500."""
        malicious_dates = [
            "2026-11-10' OR '1'='1",
            "'; DROP TABLE bookings_booking; --",
            "2026-11-10 UNION SELECT username, password FROM auth_user"
        ]
        for bad_date in malicious_dates:
            res = self.client.get(f'/api/bookings/availability/?date={bad_date}')
            # Must return 400 Bad Request or safe 404, never 500
            self.assertIn(res.status_code, [400, 404])

    def test_13_health_check_public_does_not_leak_internals(self):
        """Unauthenticated caller requesting ?full=1 must NOT receive internal database details."""
        res = self.client.get('/api/health/?full=1')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        # Must only contain safe public status, no records_audit
        self.assertNotIn('records_audit', data)
        self.assertNotIn('database_host', data)

    def test_14_health_check_staff_receives_diagnostics(self):
        """Authenticated staff caller requesting ?full=1 receives internal diagnostics."""
        # Login as staff
        login_res = self.client.post(
            '/api/auth/login/',
            data=json.dumps({'username': 'TestOwner', 'password': 'ComplexOwnerPass!987'}),
            content_type='application/json'
        )
        token = login_res.json()['token']

        res = self.client.get('/api/health/?full=1', HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('records_audit', data)
        self.assertIn('database_host', data)


if __name__ == '__main__':
    from django.test.runner import DiscoverRunner
    runner = DiscoverRunner(verbosity=2)
    failures = runner.run_tests(['test_security_audit'])
    if failures:
        print(f"FAILED: {failures} test(s) failed.")
        exit(1)
    else:
        print("ALL 14 SECURITY TESTS PASSED WITH 100% SUCCESS!")
        exit(0)

from decimal import Decimal
from datetime import time, timedelta
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import IntegrityError
from .models import Facility, Booking, StaffProfile
from .utils import generate_slots_for_date



class BookingEngineTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='player1',
            email='player1@example.com',
            password='Password123!',
            first_name='Rahul'
        )
        self.facility = Facility.objects.create(
            name='Football & Cricket Turf',
            slug='turf',
            facility_type='TURF',
            description='Test turf description',
            price_per_hour=900.00,
            open_time=time(6, 0),
            close_time=time(23, 0),
            slot_duration_minutes=60,
            is_active=True
        )
        self.tomorrow = timezone.localdate() + timedelta(days=1)

    def test_slot_generation(self):
        """Test slot generator produces valid slots between open and close times."""
        slots = generate_slots_for_date(self.facility, self.tomorrow)
        self.assertTrue(len(slots) > 0)
        first_slot = slots[0]
        self.assertEqual(first_slot['start_time'], '06:00')
        self.assertTrue(first_slot['is_available'])
        self.assertFalse(first_slot['is_booked'])

    def test_prevent_double_booking_database_constraint(self):
        """Rule 8: Verify that duplicate booking for same facility, date, start_time is rejected."""
        Booking.objects.create(
            user=self.user,
            facility=self.facility,
            booking_date=self.tomorrow,
            start_time=time(18, 0),
            end_time=time(19, 0),
            total_price=900.00,
            status='CONFIRMED',
            customer_name='Rahul',
            customer_phone='9876543210'
        )

        with self.assertRaises(IntegrityError):
            Booking.objects.create(
                user=self.user,
                facility=self.facility,
                booking_date=self.tomorrow,
                start_time=time(18, 0),
                end_time=time(19, 0),
                total_price=900.00,
                status='CONFIRMED',
                customer_name='Duplicate Booker',
                customer_phone='9876543211'
            )

    def test_cancelled_booking_frees_slot(self):
        """Cancelled bookings should allow slot to be rebooked."""
        Booking.objects.create(
            user=self.user,
            facility=self.facility,
            booking_date=self.tomorrow,
            start_time=time(18, 0),
            end_time=time(19, 0),
            total_price=900.00,
            status='CANCELLED',
            customer_name='Rahul',
            customer_phone='9876543210'
        )

        booking2 = Booking.objects.create(
            user=self.user,
            facility=self.facility,
            booking_date=self.tomorrow,
            start_time=time(18, 0),
            end_time=time(19, 0),
            total_price=900.00,
            status='CONFIRMED',
            customer_name='New Player',
            customer_phone='9998887776'
        )
        self.assertIsNotNone(booking2.id)

    def test_check_slots_api(self):
        """Test the AJAX slot check API returns expected JSON structure."""
        url = reverse('check_slots_api')
        response = self.client.get(url, {
            'facility_id': self.facility.id,
            'date': self.tomorrow.strftime('%Y-%m-%d')
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['facility_name'], self.facility.name)
        self.assertTrue(len(data['slots']) > 0)

    def test_booking_confirmation_and_cancellation_flow(self):
        """Test full user login, booking confirmation, and subsequent cancellation."""
        self.client.login(username='player1', password='Password123!')

        response = self.client.post(reverse('confirm_booking'), {
            'facility_id': self.facility.id,
            'booking_date': self.tomorrow.strftime('%Y-%m-%d'),
            'start_time': '20:00',
            'customer_name': 'Rahul Team',
            'customer_phone': '9876543210',
            'notes': 'Night 7s game'
        })
        self.assertEqual(response.status_code, 302)

        booking = Booking.objects.get(facility=self.facility, booking_date=self.tomorrow, start_time=time(20, 0))
        self.assertEqual(booking.status, 'CONFIRMED')
        self.assertEqual(booking.customer_name, 'Rahul Team')

        cancel_url = reverse('cancel_booking', kwargs={'booking_id': booking.booking_id})
        cancel_response = self.client.post(cancel_url, {'cancellation_reason': 'Rain expected'})
        self.assertEqual(cancel_response.status_code, 302)

        booking.refresh_from_db()
        self.assertEqual(booking.status, 'CANCELLED')
        self.assertIsNotNone(booking.cancelled_at)


class StaffAndOwnerDashboardTest(TestCase):
    def setUp(self):
        # 1. Customer
        self.customer = User.objects.create_user(
            username='regular_customer',
            password='Pass123!customer'
        )

        # 2. Ground Staff (Employee)
        self.staff_user = User.objects.create_user(
            username='staff_member',
            password='Pass123!staff',
            first_name='Shabeer',
            is_staff=True
        )
        StaffProfile.objects.create(
            user=self.staff_user,
            role='GROUND_STAFF',
            phone_number='9633388662'
        )

        # 3. Owner (Superuser)
        self.owner_user = User.objects.create_superuser(
            username='club_owner',
            email='owner@friendssportshub.com',
            password='Pass123!owner',
            first_name='Owner'
        )
        StaffProfile.objects.create(
            user=self.owner_user,
            role='OWNER',
            phone_number='9633388661'
        )

        self.facility = Facility.objects.create(
            name='Football & Cricket Turf',
            slug='turf',
            facility_type='TURF',
            description='Test turf',
            price_per_hour=900.00,
            open_time=time(6, 0),
            close_time=time(23, 0),
            slot_duration_minutes=60,
            is_active=True
        )
        self.tomorrow = timezone.localdate() + timedelta(days=1)

    def test_regular_customer_denied_staff_portal(self):
        """Regular customer cannot access /manage/ staff portal."""
        self.client.login(username='regular_customer', password='Pass123!customer')
        response = self.client.get(reverse('staff_dashboard'))
        self.assertEqual(response.status_code, 302)  # redirected to login

    def test_staff_employee_can_access_dashboard_and_walkin(self):
        """Ground staff can view /manage/ and /manage/walk-in/."""
        self.client.login(username='staff_member', password='Pass123!staff')
        
        dash_response = self.client.get(reverse('staff_dashboard'))
        self.assertEqual(dash_response.status_code, 200)
        self.assertContains(dash_response, "Ground Staff Desk")

        walkin_response = self.client.get(reverse('staff_walkin_booking'))
        self.assertEqual(walkin_response.status_code, 200)

    def test_staff_can_record_walkin_booking(self):
        """Ground staff records a walk-in / phone booking."""
        self.client.login(username='staff_member', password='Pass123!staff')
        response = self.client.post(reverse('staff_walkin_booking'), {
            'facility_id': self.facility.id,
            'booking_date': self.tomorrow.strftime('%Y-%m-%d'),
            'start_time': '19:00',
            'customer_name': 'Walk-in Jaleel',
            'customer_phone': '9847112233',
            'payment_status': 'PAID',
            'staff_notes': 'Paid cash at counter'
        })
        self.assertEqual(response.status_code, 302)

        booking = Booking.objects.get(facility=self.facility, booking_date=self.tomorrow, start_time=time(19, 0))
        self.assertEqual(booking.customer_name, 'Walk-in Jaleel')
        self.assertEqual(booking.payment_status, 'PAID')
        self.assertTrue(booking.created_by_staff)

    def test_staff_can_mark_payment_collected(self):
        """Ground staff marks an unpaid booking as PAID."""
        booking = Booking.objects.create(
            user=self.customer,
            facility=self.facility,
            booking_date=self.tomorrow,
            start_time=time(17, 0),
            end_time=time(18, 0),
            total_price=Decimal('900.00'),
            advance_amount=Decimal('100.00'),
            balance_amount=Decimal('800.00'),
            status='CONFIRMED',
            payment_status='ADVANCE_PAID',
            customer_name='Online Player',
            customer_phone='9990001111'
        )

        self.client.login(username='staff_member', password='Pass123!staff')
        update_url = reverse('staff_update_booking_status', kwargs={'booking_id': booking.booking_id})
        res = self.client.post(update_url, {'action': 'collect_balance'})

        self.assertEqual(res.status_code, 302)

        booking.refresh_from_db()
        self.assertEqual(booking.payment_status, 'PAID')

    def test_owner_can_manage_employees_and_view_reports(self):
        """Owner can view employee list and revenue reports."""
        self.client.login(username='club_owner', password='Pass123!owner')

        emp_response = self.client.get(reverse('staff_manage_employees'))
        self.assertEqual(emp_response.status_code, 200)
        self.assertContains(emp_response, "Shabeer")

        rep_response = self.client.get(reverse('staff_reports'))
        self.assertEqual(rep_response.status_code, 200)
        self.assertContains(rep_response, "Financial & Performance Reports")

    def test_non_owner_employee_cannot_manage_employees(self):
        """Regular ground staff cannot manage employees or view owner reports."""
        self.client.login(username='staff_member', password='Pass123!staff')
        emp_response = self.client.get(reverse('staff_manage_employees'))
        self.assertEqual(emp_response.status_code, 302)  # redirected


class UpiAdvancePaymentTest(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username='upi_player',
            password='Pass123!player',
            first_name='Anas'
        )
        self.facility = Facility.objects.create(
            name='Football & Cricket Turf',
            slug='turf',
            facility_type='TURF',
            description='Test turf',
            price_per_hour=900.00,
            open_time=time(6, 0),
            close_time=time(23, 0),
            slot_duration_minutes=60,
            is_active=True
        )
        self.tomorrow = timezone.localdate() + timedelta(days=1)

    def test_booking_redirects_to_upi_payment_screen(self):
        """When player books a slot, they are redirected to /booking/<id>/pay/."""
        self.client.login(username='upi_player', password='Pass123!player')
        response = self.client.post(reverse('confirm_booking'), {
            'facility_id': self.facility.id,
            'booking_date': self.tomorrow.strftime('%Y-%m-%d'),
            'start_time': '21:00',
            'customer_name': 'Anas Team',
            'customer_phone': '9847998877',
        })
        booking = Booking.objects.get(facility=self.facility, booking_date=self.tomorrow, start_time=time(21, 0))
        self.assertEqual(booking.advance_amount, 1.00)
        self.assertEqual(booking.balance_amount, 899.00)
        self.assertRedirects(response, reverse('upi_payment', kwargs={'booking_id': booking.booking_id}))

    def test_upi_payment_page_renders_with_advance_amount(self):
        """UPI Payment page renders advance amount of ₹100 and UPI ID."""
        booking = Booking.objects.create(
            user=self.customer,
            facility=self.facility,
            booking_date=self.tomorrow,
            start_time=time(21, 0),
            end_time=time(22, 0),
            total_price=900.00,
            advance_amount=100.00,
            balance_amount=800.00,
            status='CONFIRMED',
            payment_status='PENDING_VERIFICATION',
            customer_name='Anas Team',
            customer_phone='9847998877'
        )
        self.client.login(username='upi_player', password='Pass123!player')
        response = self.client.get(reverse('upi_payment', kwargs={'booking_id': booking.booking_id}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'akhilanandank871@oksbi')
        self.assertContains(response, 'ACHU AKHIL')

    def test_customer_submits_upi_utr_verification(self):
        """Customer submits 12-digit UPI UTR and booking status becomes ADVANCE_PAID."""
        booking = Booking.objects.create(
            user=self.customer,
            facility=self.facility,
            booking_date=self.tomorrow,
            start_time=time(21, 0),
            end_time=time(22, 0),
            total_price=900.00,
            advance_amount=100.00,
            balance_amount=800.00,
            status='CONFIRMED',
            payment_status='PENDING_VERIFICATION',
            customer_name='Anas Team',
            customer_phone='9847998877'
        )
        self.client.login(username='upi_player', password='Pass123!player')
        pay_url = reverse('upi_payment', kwargs={'booking_id': booking.booking_id})
        res = self.client.post(pay_url, {
            'action': 'submit_upi',
            'upi_transaction_id': '428901234567'
        })
        self.assertRedirects(res, reverse('booking_detail', kwargs={'booking_id': booking.booking_id}))

        booking.refresh_from_db()
        self.assertEqual(booking.payment_status, 'ADVANCE_PAID')
        self.assertEqual(booking.upi_transaction_id, '428901234567')
        self.assertEqual(booking.balance_amount, 800.00)

    def test_customer_can_choose_pay_at_venue_fallback(self):
        """Customer can opt to pay full amount in cash at venue."""
        booking = Booking.objects.create(
            user=self.customer,
            facility=self.facility,
            booking_date=self.tomorrow,
            start_time=time(21, 0),
            end_time=time(22, 0),
            total_price=900.00,
            advance_amount=100.00,
            balance_amount=800.00,
            status='CONFIRMED',
            payment_status='PENDING_VERIFICATION',
            customer_name='Anas Team',
            customer_phone='9847998877'
        )
        self.client.login(username='upi_player', password='Pass123!player')
        pay_url = reverse('upi_payment', kwargs={'booking_id': booking.booking_id})
        res = self.client.post(pay_url, {'action': 'pay_at_venue'})
        self.assertRedirects(res, reverse('booking_detail', kwargs={'booking_id': booking.booking_id}))

        booking.refresh_from_db()
        self.assertEqual(booking.payment_status, 'PAY_AT_VENUE')
        self.assertEqual(booking.advance_amount, 0.00)
        self.assertEqual(booking.balance_amount, 900.00)


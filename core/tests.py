from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from bookings.models import Facility


class CorePagesAndAuthTest(TestCase):
    def setUp(self):
        self.facility = Facility.objects.create(
            name='Football & Cricket Turf',
            slug='turf',
            facility_type='TURF',
            description='Test turf description',
            price_per_hour=900.00,
            is_active=True
        )
        self.user = User.objects.create_user(
            username='athlete',
            password='SecretPassword123!',
            email='athlete@example.com',
            first_name='Anand'
        )

    def test_public_pages_load_successfully(self):
        """Verify that all main public pages render with HTTP 200 and correct club name."""
        endpoints = ['home', 'about', 'facilities', 'pricing', 'contact', 'book_slot']
        for name in endpoints:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200, f"Page {name} failed with status {response.status_code}")
            self.assertContains(response, 'Friends Sports Hub')

    def test_customer_registration(self):
        """Verify customer registration creates user and authenticates session."""
        response = self.client.post(reverse('register'), {
            'username': 'newplayer',
            'first_name': 'Sanjay',
            'phone_number': '9847000000',
            'email': 'sanjay@example.com',
            'password': 'SecurePass123!',
            'confirm_password': 'SecurePass123!'
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='newplayer').exists())

    def test_customer_login_and_dashboard_access(self):
        """Verify login opens dashboard."""
        login_success = self.client.login(username='athlete', password='SecretPassword123!')
        self.assertTrue(login_success)

        dashboard_response = self.client.get(reverse('dashboard'))
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertContains(dashboard_response, 'Welcome, Anand')

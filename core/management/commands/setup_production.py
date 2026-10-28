import os
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from bookings.models import Facility, StaffProfile

User = get_user_model()


class Command(BaseCommand):
    help = "Bootstraps production environment with Admin credentials and default facilities"

    def handle(self, *args, **options):
        self.stdout.write("Bootstrapping production setup...")

        # 1. Ensure Admin Superuser
        admin_user, created = User.objects.get_or_create(username='Admin')
        admin_user.set_password('admin1010')
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.is_active = True
        admin_user.first_name = 'Turf'
        admin_user.last_name = 'Owner'
        admin_user.save()

        # Deactivate any other accounts for strict security
        User.objects.exclude(username__iexact='admin').update(is_active=False)

        # 2. Staff Profile
        staff_profile, _ = StaffProfile.objects.get_or_create(user=admin_user)
        staff_profile.role = 'OWNER'
        staff_profile.phone_number = '6238006820'
        staff_profile.is_approved = True
        staff_profile.save()

        self.stdout.write(self.style.SUCCESS("✅ Admin account configured: ID 'Admin'"))

        # 3. Default Facilities
        facilities_data = [
            {
                'slug': 'turf',
                'name': 'Football & Cricket Turf',
                'facility_type': 'TURF',
                'description': 'FIFA standard high-density artificial turf with professional LED floodlights for 5s/7s football and cricket.',
                'price_per_hour': Decimal('900.00'),
                'open_time': '06:00:00',
                'close_time': '23:00:00',
                'slot_duration_minutes': 60,
                'features': [
                    'FIFA Standard Artificial Grass',
                    'High Power Floodlights (Night Match)',
                    'Goal Nets & Boundary Safety Netting',
                    'Dressing Rooms & Clean Drinking Water',
                    'Ample Free Parking',
                    'Spectator Viewing Gallery'
                ],
                'is_active': True,
            },
            {
                'slug': 'swimming-pool',
                'name': 'Swimming Pool',
                'facility_type': 'POOL',
                'description': 'Hygienic, chlorinated and filtered swimming pool for fitness, practice, and recreation.',
                'price_per_hour': Decimal('150.00'),
                'open_time': '06:00:00',
                'close_time': '21:00:00',
                'slot_duration_minutes': 60,
                'features': [
                    'Filtered Fresh Water',
                    'Shower & Changing Facilities',
                    'Life Guards On-Duty'
                ],
                'is_active': True,
            },
            {
                'slug': 'childrens-park',
                'name': "Children's Park",
                'facility_type': 'PARK',
                'description': 'Fun-filled outdoor play area with swings, slides, and safety grass for kids and families.',
                'price_per_hour': Decimal('50.00'),
                'open_time': '09:00:00',
                'close_time': '20:00:00',
                'slot_duration_minutes': 60,
                'features': [
                    'Kid-Safe Playground Equipment',
                    'Shaded Seating Area for Parents',
                    'Green Lawn Environment'
                ],
                'is_active': True,
            },
        ]

        for item in facilities_data:
            fac, created = Facility.objects.get_or_create(slug=item['slug'])
            for key, val in item.items():
                setattr(fac, key, val)
            fac.save()
            status_text = "created" if created else "updated"
            self.stdout.write(f"Facility '{fac.name}' {status_text}.")

        self.stdout.write(self.style.SUCCESS("🚀 Production bootstrap completed successfully!"))

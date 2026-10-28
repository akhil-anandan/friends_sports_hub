from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from bookings.models import Facility, StaffProfile


class Command(BaseCommand):
    help = "Seed initial data for Friends Sports Hub Mulayankavu"

    def handle(self, *args, **options):
        # 1. Create or ensure superuser/owner exists
        admin_user, created = User.objects.get_or_create(
            username="admin",
            defaults={"email": "admin@friendssportshub.com", "first_name": "Hub Owner", "is_staff": True, "is_superuser": True}
        )
        if created:
            admin_user.set_password("admin123")
            admin_user.save()
            self.stdout.write(self.style.SUCCESS("Superuser 'admin' created with password 'admin123'"))
        
        StaffProfile.objects.get_or_create(
            user=admin_user,
            defaults={"role": "OWNER", "phone_number": "9633388661"}
        )

        # 2. Create demo ground employee account
        staff_user, staff_created = User.objects.get_or_create(
            username="staff_shabeer",
            defaults={"email": "shabeer@friendssportshub.com", "first_name": "Shabeer", "last_name": "(Ground Staff)", "is_staff": True}
        )
        if staff_created:
            staff_user.set_password("staff123")
            staff_user.save()
            self.stdout.write(self.style.SUCCESS("Employee 'staff_shabeer' created with password 'staff123'"))
        
        StaffProfile.objects.get_or_create(
            user=staff_user,
            defaults={"role": "GROUND_STAFF", "phone_number": "9633388662"}
        )

        # 2. Seed actual facilities
        facilities_data = [
            {
                "name": "Football & Cricket Turf",
                "slug": "turf",
                "facility_type": "TURF",
                "description": "High-grade artificial turf football and cricket ground at Friends Sports Hub Mulayankavu, Kulukkallur. Equipped with high-mast LED floodlights, netting enclosure, and changing facilities.",
                "image_static_fallback": "images/turf_hero.jpg",
                "price_per_hour": 900.00,
                "open_time": "06:00:00",
                "close_time": "23:00:00",
                "slot_duration_minutes": 60,
                "features": [
                    "All-weather synthetic turf",
                    "Cricket & 7s / 5s Football ready",
                    "Pro tournament-grade floodlights",
                    "Complete protective netting cage",
                    "Spectator seating gallery",
                    "Clean drinking water & washrooms"
                ],
                "is_active": True,
            },
            {
                "name": "Swimming Pool",
                "slug": "swimming-pool",
                "facility_type": "POOL",
                "description": "Covered hygienic swimming pool suitable for daily leisure swimming, training, and family sessions under clean chlorinated water standards.",
                "image_static_fallback": "images/hub_banner.jpg",
                "price_per_hour": 150.00,
                "open_time": "06:00:00",
                "close_time": "21:00:00",
                "slot_duration_minutes": 60,
                "features": [
                    "Indoor sheltered pool",
                    "Clean filtered water system",
                    "Separate shower & changing cabins",
                    "Life-saving ring and safety gear",
                    "Family and kids friendly"
                ],
                "is_active": True,
            },
            {
                "name": "Children's Park",
                "slug": "childrens-park",
                "facility_type": "PARK",
                "description": "Vibrant and secure outdoor play area for kids featuring multiple slides, swings, climbers, and safe outdoor activity equipment.",
                "image_static_fallback": "images/hub_banner.jpg",
                "price_per_hour": 50.00,
                "open_time": "08:00:00",
                "close_time": "20:00:00",
                "slot_duration_minutes": 60,
                "features": [
                    "Multiple colorful slides & swings",
                    "Safe outdoor play fencing",
                    "Playful toddler equipment",
                    "Family sitting benches around park"
                ],
                "is_active": True,
            },
        ]

        for item in facilities_data:
            facility, created = Facility.objects.update_or_create(
                slug=item["slug"],
                defaults=item
            )
            action = "Created" if created else "Updated"
            self.stdout.write(self.style.SUCCESS(f"{action} facility: {facility.name}"))

from django.core.management.base import BaseCommand
from bookings.services import expire_stale_bookings


class Command(BaseCommand):
    help = 'Sweeps and expires stale pending owner approval bookings that exceeded the expiration duration.'

    def handle(self, *args, **options):
        expired = expire_stale_bookings()
        if expired:
            self.stdout.write(
                self.style.SUCCESS(f"Successfully expired {len(expired)} stale pending booking(s): {', '.join(b.booking_id for b in expired)}")
            )
        else:
            self.stdout.write("No stale pending bookings to expire.")

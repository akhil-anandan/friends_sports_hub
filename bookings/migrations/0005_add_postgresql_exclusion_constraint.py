# Generated for PostgreSQL Exclusion Constraint and Concurrency Protection
from django.db import migrations
try:
    from django.contrib.postgres.operations import BtreeGistExtension
except ImportError:
    BtreeGistExtension = None


def apply_pg_exclusion_constraint(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor == 'postgresql':
        with connection.cursor() as cursor:
            # Ensure btree_gist extension exists
            cursor.execute("CREATE EXTENSION IF NOT EXISTS btree_gist;")
            # Drop existing if any, then create exclusion constraint
            cursor.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint WHERE conname = 'exclude_overlapping_active_bookings'
                    ) THEN
                        ALTER TABLE bookings_booking
                        ADD CONSTRAINT exclude_overlapping_active_bookings
                        EXCLUDE USING gist (
                            facility_id WITH =,
                            tsrange(booking_date + start_time, booking_date + end_time, '[)') WITH &&
                        )
                        WHERE (status IN ('PENDING_APPROVAL', 'APPROVED', 'CONFIRMED', 'COMPLETED'));
                    END IF;
                END $$;
            """)


def remove_pg_exclusion_constraint(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor == 'postgresql':
        with connection.cursor() as cursor:
            cursor.execute("ALTER TABLE bookings_booking DROP CONSTRAINT IF EXISTS exclude_overlapping_active_bookings;")


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0004_remove_booking_unique_active_booking_slot_and_more'),
    ]

    operations = [
        migrations.RunPython(apply_pg_exclusion_constraint, remove_pg_exclusion_constraint),
    ]

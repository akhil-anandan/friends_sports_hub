from decimal import Decimal
import uuid
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.db.models import Q



class Facility(models.Model):
    FACILITY_TYPES = [
        ('TURF', 'Sports Turf (Football / Cricket)'),
        ('POOL', 'Swimming Pool'),
        ('PARK', "Children's Park"),
        ('OTHER', 'Other Sports Activity'),
    ]

    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True, max_length=140)
    facility_type = models.CharField(max_length=20, choices=FACILITY_TYPES, default='TURF')
    description = models.TextField(help_text="Detailed description of features, ground size, and amenities.")
    image = models.ImageField(upload_to='facilities/', blank=True, null=True, help_text="Upload facility photo")
    image_static_fallback = models.CharField(max_length=200, default='images/turf_hero.jpg', help_text="Static image path if no upload provided")
    price_per_hour = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(0)], help_text="Hourly rate in INR")
    open_time = models.TimeField(default='06:00:00', help_text="Daily opening time")
    close_time = models.TimeField(default='23:00:00', help_text="Daily closing time")
    slot_duration_minutes = models.PositiveIntegerField(default=60, help_text="Slot duration in minutes")
    features = models.JSONField(default=list, blank=True, help_text="List of highlights e.g. ['FIFA standard turf', 'High power floodlights']")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Facilities'
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def image_url(self):
        if self.image:
            return self.image.url
        return f'/static/{self.image_static_fallback}'


class Booking(models.Model):
    STATUS_CHOICES = [
        ('CONFIRMED', 'Confirmed'),
        ('CANCELLED', 'Cancelled'),
        ('COMPLETED', 'Completed'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('ADVANCE_PAID', 'Advance Paid (₹100 via UPI)'),
        ('PAID', 'Fully Paid'),
        ('PENDING_VERIFICATION', 'UPI Verification Pending'),
        ('PAY_AT_VENUE', 'Pay at Venue / Cash on Arrival'),
    ]

    PAYMENT_METHOD_CHOICES = [
        ('UPI', 'UPI (GPay / PhonePe / Paytm)'),
        ('CASH', 'Cash at Counter'),
    ]

    booking_id = models.CharField(max_length=32, unique=True, editable=False, db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings')
    facility = models.ForeignKey(Facility, on_delete=models.PROTECT, related_name='bookings')
    booking_date = models.DateField(db_index=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    total_price = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(0)])
    
    # Advance UPI payment tracking
    advance_amount = models.DecimalField(max_digits=8, decimal_places=2, default=100.00, help_text="Advance paid via UPI in INR")
    balance_amount = models.DecimalField(max_digits=8, decimal_places=2, default=0.00, help_text="Balance to be collected at venue")
    upi_transaction_id = models.CharField(max_length=64, blank=True, help_text="12-digit UPI UTR / Transaction Reference")
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='UPI')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='CONFIRMED', db_index=True)
    payment_status = models.CharField(max_length=25, choices=PAYMENT_STATUS_CHOICES, default='ADVANCE_PAID')
    
    # Customer contact info captured at booking time
    customer_name = models.CharField(max_length=120)
    customer_phone = models.CharField(max_length=20)
    customer_email = models.EmailField(blank=True)
    notes = models.TextField(blank=True, help_text="Team name, notes, or special requirements")
    
    cancellation_reason = models.TextField(blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    
    created_by_staff = models.BooleanField(default=False, help_text="True if booked by counter employee")
    staff_notes = models.TextField(blank=True, help_text="Internal notes by ground staff")


    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-booking_date', '-start_time']
        constraints = [
            # Overlapping/duplicate protection: only 1 non-cancelled booking per facility, date, start_time
            models.UniqueConstraint(
                fields=['facility', 'booking_date', 'start_time'],
                condition=~Q(status='CANCELLED'),
                name='unique_active_booking_slot'
            )
        ]

    def save(self, *args, **kwargs):
        if not self.booking_id:
            date_str = timezone.now().strftime("%Y%m%d")
            unique_part = uuid.uuid4().hex[:6].upper()
            self.booking_id = f"FSH-{date_str}-{unique_part}"
        
        advance_val = Decimal(str(self.advance_amount)) if self.advance_amount is not None else Decimal('100.00')
        total_val = Decimal(str(self.total_price)) if self.total_price is not None else Decimal('0.00')
        
        if (self.balance_amount is None or self.balance_amount == 0) and total_val > advance_val:
            self.balance_amount = max(Decimal('0.00'), total_val - advance_val)
        super().save(*args, **kwargs)



    def __str__(self):
        return f"{self.booking_id} - {self.facility.name} ({self.booking_date} {self.start_time.strftime('%H:%M')})"

    @property
    def is_cancellable(self):
        """Allows cancellation if status is CONFIRMED and booking is in the future."""
        if self.status != 'CONFIRMED':
            return False
        booking_datetime = timezone.datetime.combine(self.booking_date, self.start_time)
        booking_datetime = timezone.make_aware(booking_datetime, timezone.get_current_timezone())
        return timezone.now() < booking_datetime


class StaffProfile(models.Model):
    ROLE_CHOICES = [
        ('OWNER', 'Owner / Managing Director'),
        ('MANAGER', 'Turf Manager'),
        ('GROUND_STAFF', 'Ground Staff / Booking Employee'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='staff_profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='GROUND_STAFF')
    phone_number = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['role', 'user__first_name']

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.get_role_display()})"


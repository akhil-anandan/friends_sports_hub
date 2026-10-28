from django.contrib import admin
from .models import Facility, Booking, StaffProfile


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'phone_number', 'is_active', 'created_at')
    list_filter = ('role', 'is_active')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'phone_number')


@admin.register(Facility)
class FacilityAdmin(admin.ModelAdmin):
    list_display = ('name', 'facility_type', 'price_per_hour', 'open_time', 'close_time', 'slot_duration_minutes', 'is_active')
    list_filter = ('facility_type', 'is_active')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('booking_id', 'facility', 'customer_name', 'customer_phone', 'booking_date', 'start_time', 'total_price', 'advance_amount', 'balance_amount', 'payment_status', 'status')
    list_filter = ('status', 'payment_status', 'payment_method', 'booking_date', 'facility')
    search_fields = ('booking_id', 'customer_name', 'customer_phone', 'customer_email', 'upi_transaction_id', 'user__username')
    readonly_fields = ('booking_id', 'created_at', 'updated_at', 'cancelled_at')
    ordering = ('-booking_date', '-start_time')


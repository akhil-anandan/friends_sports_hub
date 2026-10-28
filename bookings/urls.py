from django.urls import path
from . import views
from . import staff_views

urlpatterns = [
    # Public slot availability page (view-only for public users)
    path('book/', views.booking_view, name='book_slot'),
    path('book/<slug:slug>/', views.booking_view, name='book_facility_slot'),
    path('api/check-slots/', views.check_slots_api, name='check_slots_api'),

    # Admin-only booking confirmation (no payment)
    path('booking/confirm/', views.confirm_booking, name='confirm_booking'),
    path('booking/<str:booking_id>/', views.booking_detail, name='booking_detail'),
    path('booking/<str:booking_id>/cancel/', views.cancel_booking, name='cancel_booking'),

    # Owner & Staff Management Portal
    path('manage/', staff_views.staff_dashboard_view, name='staff_dashboard'),
    path('manage/walk-in/', staff_views.staff_walkin_booking_view, name='staff_walkin_booking'),
    path('manage/booking/<str:booking_id>/update/', staff_views.staff_update_booking_status, name='staff_update_booking_status'),
    path('manage/employees/', staff_views.staff_manage_employees_view, name='staff_manage_employees'),
    path('manage/employees/<int:user_id>/toggle/', staff_views.staff_toggle_employee_active, name='staff_toggle_employee_active'),
    path('manage/reports/', staff_views.staff_reports_view, name='staff_reports'),
]

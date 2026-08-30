from django.urls import path

from .api_views import (
    BookingCancelAPIView,
    BookingCheckInAPIView,
    BookingCreateAPIView,
    BookingDetailAPIView,
    BookingRescheduleAPIView,
    MyBookingListAPIView,
    StaffBookingCheckInAPIView,
)


urlpatterns = [
    path("", BookingCreateAPIView.as_view(), name="api_booking_create"),
    path("my/", MyBookingListAPIView.as_view(), name="api_my_booking_list"),
    path("<int:pk>/", BookingDetailAPIView.as_view(), name="api_booking_detail"),

    # Customer self check-in on the scheduled booking date.
    path("<int:pk>/check-in/", BookingCheckInAPIView.as_view(), name="api_booking_check_in"),

    # Reception/staff check-in uses the Day 29 role + branch permission system.
    path(
        "<int:pk>/staff-check-in/",
        StaffBookingCheckInAPIView.as_view(),
        name="api_staff_booking_check_in",
    ),

    path("<int:pk>/cancel/", BookingCancelAPIView.as_view(), name="api_booking_cancel"),
    path(
        "<int:pk>/reschedule/",
        BookingRescheduleAPIView.as_view(),
        name="api_booking_reschedule",
    ),
]

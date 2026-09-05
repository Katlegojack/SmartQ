from django.urls import path

from .api_views import (
    BookingCancelAPIView,
    BookingCheckInAPIView,
    BookingCreateAPIView,
    BookingDetailAPIView,
    BookingRescheduleAPIView,
    CustomerWalkInAPIView,
    MyBookingListAPIView,
    ReceptionBookingSearchAPIView,
    ReceptionGuestWalkInAPIView,
    StaffBookingCheckInAPIView,
)


urlpatterns = [
    path("", BookingCreateAPIView.as_view(), name="api_booking_create"),
    path("my/", MyBookingListAPIView.as_view(), name="api_my_booking_list"),
    path("walk-ins/", CustomerWalkInAPIView.as_view(), name="api_customer_walk_in"),

    # Reception workflows are placed before the integer booking routes so their
    # paths remain clear and unambiguous.
    path(
        "reception/search/",
        ReceptionBookingSearchAPIView.as_view(),
        name="api_reception_booking_search",
    ),
    path(
        "reception/walk-ins/",
        ReceptionGuestWalkInAPIView.as_view(),
        name="api_reception_guest_walk_in",
    ),

    path("<int:pk>/", BookingDetailAPIView.as_view(), name="api_booking_detail"),
    path(
        "<int:pk>/check-in/",
        BookingCheckInAPIView.as_view(),
        name="api_booking_check_in",
    ),
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

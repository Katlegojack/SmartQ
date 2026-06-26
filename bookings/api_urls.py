#path let us define url routes for this app
from django.urls import path
#Import booking creation api view
from .api_views import BookingCreateAPIView,MyBookingListAPIView,BookingDetailAPIView

#These are the booking api routes
urlpatterns = [
    # Creates a new booking for the logged-in user. Full URL: /api/v1/bookings/
    path('',BookingCreateAPIView.as_view(),name='api_booking_create'),
    # Returns bookings that belong to the logged-in user. Full URL: /api/v1/bookings/my/
    path('my/',MyBookingListAPIView.as_view(),name='api_my_booking_list'),

    # Returns one specific booking that belongs to the logged-in user.
    # Full URL example: /api/v1/bookings/5/
    path("<int:pk>/",BookingDetailAPIView.as_view(),name="api_booking_detail"),


]
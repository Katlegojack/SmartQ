#path let us define url routes for this app
from django.urls import path
#Import booking creation api view
from .api_views import BookingCreateAPIView

#These are the booking api routes
urlpatterns = [
    path('',BookingCreateAPIView.as_view(),name='api_booking_create'),
    
]
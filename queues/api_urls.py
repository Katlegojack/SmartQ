#Define URL routes
from django.urls import path
#Import queue API views
from queues.api_views import CallNextTicketAPIView


urlpatterns = [
    path('counters/<int:counter_id>/call-next/',CallNextTicketAPIView.as_view(),name='api_call_next_ticket'),
]
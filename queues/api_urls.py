#Define URL routes
from django.urls import path
#Import queue API views
from queues.api_views import CallNextTicketAPIView,CompleteCurrentTicketAPIView,NoShowCurrentTicketAPIView


urlpatterns = [
    path('counters/<int:counter_id>/call-next/',CallNextTicketAPIView.as_view(),name='api_call_next_ticket'),
    path('counters/<int:counter_id>/complete/',CompleteCurrentTicketAPIView.as_view(),name='api_complete_current_ticket'),
    path('counters/<int:counter_id>/no-show/',NoShowCurrentTicketAPIView.as_view(),name='api_no_show_current_ticket'),
]
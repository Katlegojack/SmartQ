from django.urls import path

from .api_views import (
    BranchWaitingQueueAPIView,
    CallNextTicketAPIView,
    CompleteCurrentTicketAPIView,
    CurrentCounterTicketAPIView,
    MyCurrentQueueTicketAPIView,
    NoShowCurrentTicketAPIView,
)


urlpatterns = [
    # Customer queue tracker: current ticket + position + estimated wait.
    path("my-current/", MyCurrentQueueTicketAPIView.as_view(), name="api_my_current_queue_ticket"),

    # Staff read APIs used by the counter/reception dashboards.
    path(
        "branches/<int:branch_id>/waiting/",
        BranchWaitingQueueAPIView.as_view(),
        name="api_branch_waiting_queue",
    ),
    path(
        "counters/<int:counter_id>/current/",
        CurrentCounterTicketAPIView.as_view(),
        name="api_current_counter_ticket",
    ),

    # Staff queue-operation APIs.
    path(
        "counters/<int:counter_id>/call-next/",
        CallNextTicketAPIView.as_view(),
        name="api_call_next_ticket",
    ),
    path(
        "counters/<int:counter_id>/complete/",
        CompleteCurrentTicketAPIView.as_view(),
        name="api_complete_current_ticket",
    ),
    path(
        "counters/<int:counter_id>/no-show/",
        NoShowCurrentTicketAPIView.as_view(),
        name="api_no_show_current_ticket",
    ),
]

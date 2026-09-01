from django.urls import path

from .api_views import (
    BranchQueueEventAuditAPIView,
    BranchWaitingQueueAPIView,
    CallNextTicketAPIView,
    CompleteCurrentTicketAPIView,
    CurrentCounterTicketAPIView,
    CustomerBookingTimelineAPIView,
    MyCurrentQueueTicketAPIView,
    NoShowCurrentTicketAPIView,
)
from .reporting_api import BranchOperationalReportAPIView


urlpatterns = [
    # Customer queue tracker: current ticket + position + estimated wait.
    path("my-current/", MyCurrentQueueTicketAPIView.as_view(), name="api_my_current_queue_ticket"),

    # Customer-owned append-only lifecycle history for one booking.
    path(
        "bookings/<int:booking_id>/timeline/",
        CustomerBookingTimelineAPIView.as_view(),
        name="api_customer_booking_timeline",
    ),

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

    # Manager/System Admin historical operational audit timeline.
    path(
        "branches/<int:branch_id>/events/",
        BranchQueueEventAuditAPIView.as_view(),
        name="api_branch_queue_event_audit",
    ),

    # Manager/System Admin historical QueueEvent reporting.
    path(
        "branches/<int:branch_id>/reports/operational/",
        BranchOperationalReportAPIView.as_view(),
        name="api_branch_operational_report",
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

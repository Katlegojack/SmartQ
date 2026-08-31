from collections import Counter as PythonCounter

from django.db.models import Count
from django.utils import timezone

from bookings.models import Booking
from counters.models import Counter
from queues.models import QueueTicket
from queues.statistics import get_branch_daily_report


def get_booking_source_summary(branch, booking_date):
    """Return online-vs-walk-in booking counts for one branch/date."""
    rows = (
        Booking.objects.filter(branch=branch, booking_date=booking_date)
        .values("source")
        .annotate(total=Count("id"))
    )
    counts = {row["source"]: row["total"] for row in rows}
    return {
        "online": counts.get(Booking.ONLINE, 0),
        "walk_in": counts.get(Booking.WALK_IN, 0),
    }


def get_check_in_summary(branch, booking_date):
    """Return how many bookings have or have not entered the live queue."""
    bookings = Booking.objects.filter(branch=branch, booking_date=booking_date)
    total = bookings.count()
    checked_in = bookings.filter(checked_in_at__isnull=False).count()
    return {
        "checked_in": checked_in,
        "not_checked_in": total - checked_in,
    }


def get_service_distribution(branch, booking_date):
    """Return the number of bookings handled by each service for a branch/date."""
    rows = (
        Booking.objects.filter(branch=branch, booking_date=booking_date)
        .values("service_id", "service__service_code", "service__name")
        .annotate(total=Count("id"))
        .order_by("service__name")
    )
    return [
        {
            "service_id": row["service_id"],
            "service_code": row["service__service_code"],
            "service_name": row["service__name"],
            "customers": row["total"],
        }
        for row in rows
    ]


def get_counter_dashboard(branch):
    """
    Return the branch's current counter totals and per-counter operational state.

    Counter lifecycle history is not persisted yet, so this section is explicitly
    live/current even when the requested dashboard date is historical.

    Counters and currently-serving tickets are bulk-fetched. A ticket lookup map
    avoids executing one database query per counter (the classic N+1 problem).
    """
    counters = list(
        Counter.objects.filter(branch=branch)
        .select_related("assigned_staff")
        .order_by("counter_number", "id")
    )

    serving_tickets = QueueTicket.objects.filter(
        assigned_counter__branch=branch,
        status=QueueTicket.SERVING,
    ).select_related(
        "booking",
        "booking__service",
        "booking__user",
        "booking__guest_customer",
        "assigned_counter",
    )

    ticket_by_counter_id = {
        ticket.assigned_counter_id: ticket
        for ticket in serving_tickets
    }

    status_counts = PythonCounter(counter.status for counter in counters)
    staffed = sum(1 for counter in counters if counter.assigned_staff_id is not None)
    busy = sum(1 for counter in counters if counter.id in ticket_by_counter_id)
    free = sum(
        1
        for counter in counters
        if counter.status == Counter.OPEN
        and counter.assigned_staff_id is not None
        and counter.id not in ticket_by_counter_id
    )

    items = []
    for counter in counters:
        ticket = ticket_by_counter_id.get(counter.id)
        current_customer = None
        if ticket is not None:
            current_customer = {
                "ticket_id": ticket.id,
                "queue_number": ticket.queue_number,
                "customer_name": ticket.booking.customer_display_name,
                "service": ticket.booking.service.name,
            }

        items.append(
            {
                "id": counter.id,
                "counter_number": counter.counter_number,
                "queue_type": counter.queue_type,
                "status": counter.status,
                "is_staffed": counter.assigned_staff_id is not None,
                "assigned_staff_id": counter.assigned_staff_id,
                "assigned_staff_username": (
                    counter.assigned_staff.username
                    if counter.assigned_staff_id is not None
                    else None
                ),
                "is_busy": ticket is not None,
                "current_customer": current_customer,
            }
        )

    return {
        "scope": "live_current_state",
        "generated_at": timezone.now(),
        "summary": {
            "total": len(counters),
            "open": status_counts.get(Counter.OPEN, 0),
            "paused": status_counts.get(Counter.PAUSED, 0),
            "closed": status_counts.get(Counter.CLOSED, 0),
            "staffed": staffed,
            "unstaffed": len(counters) - staffed,
            "free": free,
            "busy": busy,
        },
        "counters": items,
    }


def get_manager_dashboard(branch, booking_date):
    """
    Build Smart Q's manager dashboard read model from authoritative domain data.

    No dashboard state is persisted. Date-scoped customer/queue/service values are
    derived from Booking and QueueTicket. Counter state is labelled separately as
    live because historical counter transitions are not persisted yet.
    """
    queue_report = get_branch_daily_report(branch, booking_date)

    return {
        "branch": {
            "id": branch.id,
            "branch_code": branch.branch_code,
            "name": branch.name,
            "city": branch.city,
            "opening_time": branch.opening_time,
            "closing_time": branch.closing_time,
        },
        "date": booking_date,
        "customers": queue_report["activity_summary"],
        "queue_statistics": queue_report["queue_statistics"],
        "lifecycle_totals": queue_report["totals"],
        "booking_sources": get_booking_source_summary(branch, booking_date),
        "check_in": get_check_in_summary(branch, booking_date),
        "services": get_service_distribution(branch, booking_date),
        "counters": get_counter_dashboard(branch),
    }

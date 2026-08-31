from django.db.models import Count, Q

from .models import QueueTicket


LIFECYCLE_KEYS = [
    "scheduled",
    "waiting",
    "serving",
    "completed",
    "no_show",
    "cancelled",
]


def empty_lifecycle_statistics():
    """Return a fresh zero-value lifecycle dictionary."""
    return {key: 0 for key in LIFECYCLE_KEYS}


def lifecycle_count_annotations():
    """
    Return reusable conditional Count expressions for QueueTicket lifecycle states.

    Day 34 uses conditional aggregation so one grouped database query can calculate
    all lifecycle counts instead of issuing one COUNT query per status.
    """
    return {
        "scheduled": Count("id", filter=Q(status=QueueTicket.SCHEDULED)),
        "waiting": Count("id", filter=Q(status=QueueTicket.WAITING)),
        "serving": Count("id", filter=Q(status=QueueTicket.SERVING)),
        "completed": Count("id", filter=Q(status=QueueTicket.COMPLETED)),
        "no_show": Count("id", filter=Q(status=QueueTicket.NO_SHOW)),
        "cancelled": Count("id", filter=Q(status=QueueTicket.CANCELLED)),
    }


def get_queue_statistics(branch, queue_type, booking_date):
    """Return lifecycle counts for one branch, queue type, and date."""
    result = QueueTicket.objects.filter(
        booking__branch=branch,
        booking__booking_date=booking_date,
        queue_type=queue_type,
    ).aggregate(**lifecycle_count_annotations())

    return {key: result.get(key, 0) or 0 for key in LIFECYCLE_KEYS}


def get_branch_queue_statistics(branch, booking_date):
    """
    Return separate General and Priority lifecycle counts for one branch/date.

    The query groups by queue_type and calculates every status using conditional
    aggregation. This keeps dashboard reads predictable as ticket volume grows.
    """
    statistics = {
        QueueTicket.GENERAL: empty_lifecycle_statistics(),
        QueueTicket.PRIORITY: empty_lifecycle_statistics(),
    }

    rows = (
        QueueTicket.objects.filter(
            booking__branch=branch,
            booking__booking_date=booking_date,
        )
        .values("queue_type")
        .annotate(**lifecycle_count_annotations())
    )

    for row in rows:
        queue_type = row["queue_type"]
        if queue_type not in statistics:
            continue
        statistics[queue_type] = {
            key: row.get(key, 0) or 0
            for key in LIFECYCLE_KEYS
        }

    return statistics


def combine_queue_statistics(branch_stats):
    """Combine General and Priority statistics without another database query."""
    return {
        key: (
            branch_stats[QueueTicket.GENERAL][key]
            + branch_stats[QueueTicket.PRIORITY][key]
        )
        for key in LIFECYCLE_KEYS
    }


def build_activity_summary(totals):
    """Build manager-friendly activity totals from lifecycle counts."""
    # SCHEDULED bookings exist today but have not entered the live queue yet.
    active_customers = totals["waiting"] + totals["serving"]
    resolved_customers = (
        totals["completed"] + totals["no_show"] + totals["cancelled"]
    )

    return {
        "scheduled_customers": totals["scheduled"],
        "active_customers": active_customers,
        "resolved_customers": resolved_customers,
        "total_customers": (
            totals["scheduled"] + active_customers + resolved_customers
        ),
    }


def get_branch_daily_totals(branch, booking_date):
    """Return combined General/Priority lifecycle counts for one branch/date."""
    branch_stats = get_branch_queue_statistics(branch, booking_date)
    return combine_queue_statistics(branch_stats)


def get_branch_activity_summary(branch, booking_date):
    """Return scheduled, active, resolved, and total customer counts."""
    totals = get_branch_daily_totals(branch, booking_date)
    return build_activity_summary(totals)


def get_branch_daily_report(branch, booking_date):
    """
    Return the daily queue report used by manager dashboards.

    The grouped queue statistics are calculated once and then reused to derive
    totals and the activity summary in Python.
    """
    branch_stats = get_branch_queue_statistics(branch, booking_date)
    totals = combine_queue_statistics(branch_stats)

    return {
        "branch": branch.name,
        "date": booking_date,
        "queue_statistics": branch_stats,
        "totals": totals,
        "activity_summary": build_activity_summary(totals),
    }

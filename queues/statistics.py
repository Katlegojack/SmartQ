from .models import QueueTicket


def get_queue_statistics(branch, queue_type, booking_date):
    """Return lifecycle counts for one branch, queue type, and date."""
    tickets = QueueTicket.objects.filter(
        booking__branch=branch,
        booking__booking_date=booking_date,
        queue_type=queue_type,
    )

    return {
        "scheduled": tickets.filter(status=QueueTicket.SCHEDULED).count(),
        "waiting": tickets.filter(status=QueueTicket.WAITING).count(),
        "serving": tickets.filter(status=QueueTicket.SERVING).count(),
        "completed": tickets.filter(status=QueueTicket.COMPLETED).count(),
        "no_show": tickets.filter(status=QueueTicket.NO_SHOW).count(),
        "cancelled": tickets.filter(status=QueueTicket.CANCELLED).count(),
    }


def get_branch_queue_statistics(branch, booking_date):
    """Return separate General and Priority statistics for a branch."""
    return {
        "general": get_queue_statistics(branch, QueueTicket.GENERAL, booking_date),
        "priority": get_queue_statistics(branch, QueueTicket.PRIORITY, booking_date),
    }


def get_branch_daily_totals(branch, booking_date):
    branch_stats = get_branch_queue_statistics(branch, booking_date)

    return {
        key: branch_stats["general"][key] + branch_stats["priority"][key]
        for key in ["scheduled", "waiting", "serving", "completed", "no_show", "cancelled"]
    }


def get_branch_activity_summary(branch, booking_date):
    totals = get_branch_daily_totals(branch, booking_date)

    # Scheduled appointments are expected today but are not yet in the physical queue.
    active_customers = totals["waiting"] + totals["serving"]
    resolved_customers = totals["completed"] + totals["no_show"] + totals["cancelled"]

    return {
        "scheduled_customers": totals["scheduled"],
        "active_customers": active_customers,
        "resolved_customers": resolved_customers,
        "total_customers": totals["scheduled"] + active_customers + resolved_customers,
    }


def get_branch_daily_report(branch, booking_date):
    """Return the combined branch report used by future manager dashboards."""
    return {
        "branch": branch.name,
        "date": booking_date,
        "queue_statistics": get_branch_queue_statistics(branch, booking_date),
        "totals": get_branch_daily_totals(branch, booking_date),
        "activity_summary": get_branch_activity_summary(branch, booking_date),
    }

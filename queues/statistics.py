from .models import QueueTicket

def  get_queue_statistics(branch,queue_type,booking_date):
    tickets = QueueTicket.objects.filter(
        booking__branch = branch,
        booking__booking_date =booking_date,
        queue_type = queue_type,

    )
    return{
        'waiting':tickets.filter(status=QueueTicket.WAITING).count(),
        'serving':tickets.filter(status=QueueTicket.SERVING).count(),
        'completed':tickets.filter(status=QueueTicket.COMPLETED).count(),
        'no_show':tickets.filter(status=QueueTicket.NO_SHOW).count(),
        'cancelled':tickets.filter(status=QueueTicket.CANCELLED).count(),
    }

def get_queue_branch_statistics(branch,booking_date):
    return {
        'general':get_queue_statistics(branch,QueueTicket.GENERAL,booking_date),
        'priority':get_queue_statistics(branch,QueueTicket.PRIORITY,booking_date),
    }

def get_branch_daily_totals(branch, booking_date):
    branch_stats = get_branch_queue_statistics(
        branch,
        booking_date
    )

    return {
        "waiting": branch_stats["general"]["waiting"] + branch_stats["priority"]["waiting"],
        "serving": branch_stats["general"]["serving"] + branch_stats["priority"]["serving"],
        "completed": branch_stats["general"]["completed"] + branch_stats["priority"]["completed"],
        "no_show": branch_stats["general"]["no_show"] + branch_stats["priority"]["no_show"],
        "cancelled": branch_stats["general"]["cancelled"] + branch_stats["priority"]["cancelled"],
    }

def get_branch_daily_report(branch, booking_date):
    return {
        "branch": branch.name,
        "date": booking_date,
        "queue_statistics": get_branch_queue_statistics(
            branch,
            booking_date
        ),
        "totals": get_branch_daily_totals(
            branch,
            booking_date
        ),
        "activity_summary": get_branch_activity_summary(
            branch,
            booking_date
        ),
    }

def get_branch_activity_summary(branch,booking_date):
    totals =get_branch_daily_totals(branch,booking_date)
    active_customers = totals["waiting"]+ totals["serving"]
    resolved_customers = (
        totals["completed"]
        + totals["no_show"]
        + totals["cancelled"]
    )

    total_customers = active_customers + resolved_customers

    return {
        "active_customers": active_customers,
        "resolved_customers": resolved_customers,
        "total_customers": total_customers,
    }
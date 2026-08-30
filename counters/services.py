from .models import Counter
from queues.models import QueueTicket


def get_active_counter_count(branch, queue_type):
    """Return the number of OPEN counters serving a queue type at a branch."""
    return Counter.objects.filter(
        branch=branch,
        queue_type=queue_type,
        status=Counter.OPEN,
    ).count()


def get_current_ticket(counter):
    """Return the ticket currently being served at this counter, if any."""
    return QueueTicket.objects.filter(
        assigned_counter=counter,
        status=QueueTicket.SERVING,
    ).first()


def is_counter_free(counter):
    return get_current_ticket(counter) is None


def get_free_counters(branch, queue_type):
    """Return OPEN counters that are not currently serving a customer."""
    counters = Counter.objects.filter(
        branch=branch,
        queue_type=queue_type,
        status=Counter.OPEN,
    )

    return [counter for counter in counters if is_counter_free(counter)]


def get_free_counter_count(branch, queue_type):
    return len(get_free_counters(branch, queue_type))


def get_counter_status_summary(branch, queue_type):
    """Return simple capacity numbers for manager/staff dashboards."""
    open_counters = get_active_counter_count(branch, queue_type)
    free_counters = get_free_counter_count(branch, queue_type)
    busy_counters = open_counters - free_counters

    return {
        "queue_type": queue_type,
        "open_counters": open_counters,
        "free_counters": free_counters,
        "busy_counters": busy_counters,
    }

from .models import Counter
from queues.models import QueueTicket


def get_active_counter_count(branch, queue_type):
    return Counter.objects.filter(
        branch=branch,
        queue_type=queue_type,
        status=Counter.OPEN
    ).count()

def get_current_ticket(counter):
    return QueueTicket.objects.filter(
        assinged_counter =counter,
        status = QueueTicket.SERVING
    ).first()

def is_counter_free(counter):
    current_ticket = get_current_ticket(counter)

    return current_ticket is None

def get_free_counters(branch,queue_type):
    free_counters = []

    counters = Counter.objects.filter(
        branch= branch,
        queue_type = queue_type,
        status = Counter.OPEN
    )
    for counter in counters:
        if is_counter_free(counter):
            free_counters.append(counter)
    return free_counters


def get_free_counter_count(branch,queue_type):
    return len(get_free_counters(branch,queue_type))


def get_counter_status_summary(branch,queue_type):
    open_counters = Counter.objects.filter(
        branch=branch,
        queue_type = queue_type,
        status = Counter.OPEN
    ).count()

    free_counters =get_free_counters(branch,queue_type)
    
    busy_counters = open_counters-free_counters
    
    return {
        'queue_type':queue_type,
        "open_counters" :open_counters,
        "free_counters":free_counters,
        "busy_counters":busy_counters,
    }
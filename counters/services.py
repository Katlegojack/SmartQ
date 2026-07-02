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

#Business logic to call next waiting customer on a counter
def call_next_ticket(counter):
    """
    Finds the next waiting queue ticket for the given counter,
    assigns it to the counter and marks it as SERVING.

    Returns:
        QueueTicket if one is found.
        None if no customers are waiting.
    """

    # Look for the next waiting ticket that matches this counter's queue type.
    ticket = (
        QueueTicket.objects.filter(
            queue_type=counter.queue_type,
            status = QueueTicket.WAITING,
            booking__branch =counter.branch                  
            ).order_by('id').first()     
    )

    #No waiting customers
    ticket.assigned_counter =counter
    #Customer is now being served
    ticket.status = QueueTicket.SERVING
    #Save only the changed fields
    ticket.save(update_fields=['assigned_counter','status'])

    return ticket


     
    
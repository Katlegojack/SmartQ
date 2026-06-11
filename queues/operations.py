from django.utils import timezone

from .models import QueueTicket

def call_next_customer(counter,booking_date=None):
    if booking_date is None:
        booking_date = timezone.now().date()

    current_ticket =QueueTicket.object.filter(
        assigned_counter = counter,
        status = QueueTicket.SERVING
    ).first()

    if current_ticket:
        return None

    next_ticket = QueueTicket.objects.filter(
        booking__branch = counter.branch,
        booking__booking_date = booking_date,
        queue_type = counter.queue_type,
        status = QueueTicket.WAITING
    ).order_by("-created_at").first()

    if next_ticket ==None:
        return None
    
    next_ticket.status = QueueTicket.SERVING
    next_ticket.assigned_counter = counter
    next_ticket.save()

    return next_ticket

def complete_customer(ticket):
    if ticket is None:
        return None
    
    if ticket.status != QueueTicket.SERVING:
        return None
    
    ticket.status =QueueTicket.COMPLETED
    ticket.assigned_counter = None
    ticket.save()

    return ticket

def mark_no_show(ticket):
    if ticket is None:
        return None
    if ticket.status != QueueTicket.SERVING:
        return None
    
    ticket.status =QueueTicket.NO_SHOW
    ticket.assigned_counter = None
    ticket.save()
    return ticket
    
def cancel_ticket(ticket):
    if ticket is None:
        return None
    if ticket.status not in [QueueTicket.WAITING, QueueTicket.SERVING]:
        return None
    
    ticket.status = QueueTicket.CANCELLED
    ticket.assigned_counter = None
    ticket.save()
    return ticket

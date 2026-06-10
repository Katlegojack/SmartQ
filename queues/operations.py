from django.utils import timezone

from .models import QueueTicket

def call_next_customer(branch,queue_type,booking_date=None):
    if booking_date ==None:
        booking_date = timezone.now().date()

    next_ticket = QueueTicket.objects.filter(
        booking__branch = branch,
        booking__booking_date = booking_date,
        queue_type = queue_type,
        status = QueueTicket.WAITING
    ).order_by("-created_at").first()

    if next_ticket ==None:
        return None
    
    next_ticket.status = QueueTicket.SERVING
    next_ticket.save()

    return next_ticket

def complete_customer(ticket):
    if ticket is None:
        return None
    
    if ticket.status != QueueTicket.SERVING:
        return None
    
    ticket.status =QueueTicket.COMPLETED
    ticket.save()

    return ticket

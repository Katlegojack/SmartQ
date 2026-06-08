from .models import QueueTicket

def generate_queue_number(booking,queue_type):
    prefix = "A" if queue_type == QueueTicket.GENERAL else "P"

    latest_ticket = QueueTicket.objects.filter(
        booking_brunch = booking.branch,
        booking_booking_date =booking.booking_date,
        queue_type = queue_type
    ).order_by("-id").first()

    if latest_ticket:
        last_number = int(latest_ticket.queue_number[1:])
        new_number = last_number +1
    else:
        last_number = 1
        
        return f"{prefix}{new_number:03d}"
    
def create_queue_ticket_for_booking(booking,queue_type=QueueTicket.GENERAL):
        queue_number = generate_queue_number(booking,queue_type)

        queue_ticket =QueueTicket.objects.create(
            booking = booking,
            queue_type = queue_type,
            queue_number = queue_number,
            status = QueueTicket.WAITING
        )

        return queue_ticket
        
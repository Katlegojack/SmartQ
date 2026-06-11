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
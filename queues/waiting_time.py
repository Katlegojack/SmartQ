from counters.services import get_active_counter_count
from queues.models import QueueTicket


def get_people_ahead(ticket):
    """Count checked-in waiting customers who entered this queue before the ticket."""
    checked_in_at = ticket.booking.checked_in_at
    if checked_in_at is None:
        return 0

    return QueueTicket.objects.filter(
        booking__branch=ticket.booking.branch,
        booking__booking_date=ticket.booking.booking_date,
        booking__checked_in_at__isnull=False,
        queue_type=ticket.queue_type,
        status=QueueTicket.WAITING,
        booking__checked_in_at__lt=checked_in_at,
    ).count()


def get_queue_position(ticket):
    return get_people_ahead(ticket) + 1


def calculate_estimated_wait_time(ticket):
    branch = ticket.booking.branch
    service = ticket.booking.service

    active_counters = get_active_counter_count(branch, ticket.queue_type)

    if active_counters == 0:
        return None

    people_ahead = get_people_ahead(ticket)
    estimated_wait_time = (people_ahead * service.average_service_time) / active_counters

    return round(estimated_wait_time)


def get_ticket_prediction(ticket):
    return {
        "queue_number": ticket.queue_number,
        "queue_type": ticket.queue_type,
        "people_ahead": get_people_ahead(ticket),
        "queue_position": get_queue_position(ticket),
        "estimated_wait_time": calculate_estimated_wait_time(ticket),
    }

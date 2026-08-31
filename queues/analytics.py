from .models import QueueEvent


def get_ticket_actual_wait_minutes(ticket):
    """
    Return actual live-queue wait from CHECKED_IN to CALLED, or None if incomplete.

    This is intentionally narrower than "service time". Smart Q does not yet
    persist a separate face-to-face SERVICE_STARTED event, so Day 36 must not
    relabel CALLED->COMPLETED as actual service duration.
    """
    if ticket is None:
        return None

    checked_in = QueueEvent.objects.filter(
        ticket=ticket,
        event_type=QueueEvent.CHECKED_IN,
    ).order_by("occurred_at", "id").first()
    if checked_in is None:
        return None

    called = QueueEvent.objects.filter(
        ticket=ticket,
        event_type=QueueEvent.CALLED,
        occurred_at__gte=checked_in.occurred_at,
    ).order_by("occurred_at", "id").first()
    if called is None:
        return None

    seconds = (called.occurred_at - checked_in.occurred_at).total_seconds()
    return round(max(seconds, 0) / 60, 2)

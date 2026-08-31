from accounts.permissions import get_user_profile

from .models import QueueEvent


def get_event_source(actor):
    """Classify an event actor without coupling event writes to HTTP views."""
    if actor is None or not getattr(actor, "is_authenticated", False):
        return QueueEvent.SYSTEM

    profile = get_user_profile(actor)
    if profile is not None and profile.role == profile.CUSTOMER:
        return QueueEvent.CUSTOMER
    return QueueEvent.STAFF


def record_queue_event(
    event_type,
    *,
    ticket=None,
    booking=None,
    counter=None,
    actor=None,
    source=None,
    from_ticket_status="",
    to_ticket_status="",
    from_booking_status="",
    to_booking_status="",
    metadata=None,
    occurred_at=None,
):
    """
    Append one non-sensitive operational fact to the Smart Q event timeline.

    Snapshot fields intentionally preserve human-readable audit context even if
    the linked user later changes username/role or a ticket changes queue number.
    Sensitive priority inputs such as pregnancy/disability must not be written to
    metadata.
    """
    if booking is None and ticket is not None:
        booking = ticket.booking

    if counter is None and ticket is not None:
        counter = ticket.assigned_counter

    branch = None
    service = None
    if booking is not None:
        branch = booking.branch
        service = booking.service
    elif counter is not None:
        branch = counter.branch

    actor_username = ""
    actor_role = ""
    if actor is not None and getattr(actor, "is_authenticated", False):
        actor_username = actor.get_username()
        profile = get_user_profile(actor)
        if profile is not None:
            actor_role = profile.role

    kwargs = {
        "event_type": event_type,
        "ticket": ticket,
        "booking": booking,
        "counter": counter,
        "branch": branch,
        "service": service,
        "actor": actor if actor is not None and getattr(actor, "is_authenticated", False) else None,
        "source": source or get_event_source(actor),
        "actor_username": actor_username,
        "actor_role": actor_role,
        "from_ticket_status": from_ticket_status or "",
        "to_ticket_status": to_ticket_status or "",
        "from_booking_status": from_booking_status or "",
        "to_booking_status": to_booking_status or "",
        "queue_number": ticket.queue_number if ticket is not None else "",
        "queue_type": ticket.queue_type if ticket is not None else "",
        "metadata": metadata or {},
    }
    if occurred_at is not None:
        kwargs["occurred_at"] = occurred_at

    return QueueEvent.objects.create(**kwargs)


def get_ticket_event_timeline(ticket):
    """Return a ticket's append-only events in chronological order."""
    if ticket is None:
        return QueueEvent.objects.none()
    return QueueEvent.objects.filter(ticket=ticket).select_related(
        "booking", "counter", "branch", "service", "actor"
    ).order_by("occurred_at", "id")


def get_booking_event_timeline(booking):
    """Return all queue events connected to one booking."""
    if booking is None:
        return QueueEvent.objects.none()
    return QueueEvent.objects.filter(booking=booking).select_related(
        "ticket", "counter", "branch", "service", "actor"
    ).order_by("occurred_at", "id")


def get_counter_event_timeline(counter):
    """Return counter lifecycle history for later historical reconstruction."""
    if counter is None:
        return QueueEvent.objects.none()
    return QueueEvent.objects.filter(counter=counter).select_related(
        "ticket", "booking", "branch", "service", "actor"
    ).order_by("occurred_at", "id")

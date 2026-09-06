import math

from django.db.models import Q
from django.utils import timezone

from counters.models import Counter
from queues.models import QueueTicket


def _service_target_seconds(ticket):
    """Return the immutable target captured at service start, or the current service average."""
    if ticket.service_target_seconds is not None:
        return max(int(ticket.service_target_seconds), 0)

    average_minutes = ticket.booking.service.average_service_time or 0
    return max(int(round(average_minutes * 60)), 0)


def get_service_clock(ticket, now=None):
    """Return live elapsed/remaining service timing for a ticket."""
    if now is None:
        now = timezone.now()

    target_seconds = _service_target_seconds(ticket)
    started_at = ticket.service_started_at

    if started_at is None:
        elapsed_seconds = 0
    else:
        ended_at = ticket.service_completed_at or now
        elapsed_seconds = max(int((ended_at - started_at).total_seconds()), 0)

    return {
        "service_started_at": started_at,
        "service_target_seconds": target_seconds,
        "service_elapsed_seconds": elapsed_seconds,
        "service_remaining_seconds": max(target_seconds - elapsed_seconds, 0),
        "service_overrun_seconds": max(elapsed_seconds - target_seconds, 0),
    }


def _waiting_ahead_queryset(ticket):
    """Return same-queue waiting customers who entered before this ticket."""
    checked_in_at = ticket.booking.checked_in_at
    if checked_in_at is None:
        return QueueTicket.objects.none()

    return QueueTicket.objects.filter(
        booking__branch=ticket.booking.branch,
        booking__booking_date=ticket.booking.booking_date,
        booking__checked_in_at__isnull=False,
        queue_type=ticket.queue_type,
        status=QueueTicket.WAITING,
        assigned_counter__isnull=True,
    ).filter(
        Q(booking__checked_in_at__lt=checked_in_at)
        | Q(booking__checked_in_at=checked_in_at, id__lt=ticket.id)
    ).select_related("booking", "booking__service").order_by("booking__checked_in_at", "id")


def _serving_ahead_queryset(ticket):
    """Return customers already being served by the same branch/queue type."""
    return QueueTicket.objects.filter(
        booking__branch=ticket.booking.branch,
        booking__booking_date=ticket.booking.booking_date,
        queue_type=ticket.queue_type,
        status=QueueTicket.SERVING,
    ).select_related("booking", "booking__service", "assigned_counter")


def get_people_ahead(ticket):
    """Count waiting-ahead plus currently served customers for a live queue ticket."""
    if ticket.status == QueueTicket.SERVING:
        return 0

    return _waiting_ahead_queryset(ticket).count() + _serving_ahead_queryset(ticket).count()


def get_queue_position(ticket):
    if ticket.status == QueueTicket.SERVING:
        return 0
    return get_people_ahead(ticket) + 1


def calculate_estimated_wait_seconds(ticket, now=None):
    """
    Estimate time until this waiting customer can start service.

    Smart Q now uses live counter availability rather than multiplying a static
    queue position by one average. Busy counters contribute only their remaining
    target time, idle OPEN counters are available immediately, and waiting
    customers ahead are scheduled onto whichever matching counter becomes free
    first. The browser can then tick this seconds value down locally between API
    refreshes.
    """
    if ticket.status == QueueTicket.SERVING:
        return 0
    if ticket.booking.checked_in_at is None:
        return 0
    if now is None:
        now = timezone.now()

    serving = list(_serving_ahead_queryset(ticket))
    waiting_ahead = list(_waiting_ahead_queryset(ticket))

    open_counter_ids = set(
        Counter.objects.filter(
            branch=ticket.booking.branch,
            queue_type=ticket.queue_type,
            status=Counter.OPEN,
        ).values_list("id", flat=True)
    )
    for serving_ticket in serving:
        if serving_ticket.assigned_counter_id is not None:
            open_counter_ids.add(serving_ticket.assigned_counter_id)

    # One availability bucket per usable physical counter. A virtual bucket
    # preserves the deterministic fallback for branches that have not opened a
    # counter yet instead of returning an unusable infinity/null ETA.
    counter_available_seconds = {counter_id: 0 for counter_id in open_counter_ids}
    virtual_counter_index = 0

    for serving_ticket in serving:
        remaining = get_service_clock(serving_ticket, now=now)["service_remaining_seconds"]
        counter_id = serving_ticket.assigned_counter_id
        if counter_id is None:
            counter_id = f"virtual-{virtual_counter_index}"
            virtual_counter_index += 1
        counter_available_seconds[counter_id] = max(
            counter_available_seconds.get(counter_id, 0),
            remaining,
        )

    if not counter_available_seconds:
        counter_available_seconds["virtual-0"] = 0

    for ahead_ticket in waiting_ahead:
        counter_id = min(counter_available_seconds, key=counter_available_seconds.get)
        counter_available_seconds[counter_id] += _service_target_seconds(ahead_ticket)

    return max(min(counter_available_seconds.values()), 0)


def calculate_estimated_wait_time(ticket, now=None):
    """Backward-compatible whole-minute ETA derived from the live seconds estimate."""
    seconds = calculate_estimated_wait_seconds(ticket, now=now)
    return int(math.ceil(seconds / 60)) if seconds else 0


def get_ticket_prediction(ticket, now=None):
    if now is None:
        now = timezone.now()

    service_clock = get_service_clock(ticket, now=now)
    estimated_wait_seconds = calculate_estimated_wait_seconds(ticket, now=now)

    return {
        "queue_number": ticket.queue_number,
        "queue_type": ticket.queue_type,
        "people_ahead": get_people_ahead(ticket),
        "queue_position": get_queue_position(ticket),
        "estimated_wait_time": int(math.ceil(estimated_wait_seconds / 60)) if estimated_wait_seconds else 0,
        "estimated_wait_seconds": estimated_wait_seconds,
        "prediction_generated_at": now,
        **service_clock,
    }

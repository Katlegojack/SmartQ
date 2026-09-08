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
    """Return same-lane waiting customers who entered before this ticket."""
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


def _serving_same_lane_queryset(ticket):
    return QueueTicket.objects.filter(
        booking__branch=ticket.booking.branch,
        booking__booking_date=ticket.booking.booking_date,
        queue_type=ticket.queue_type,
        status=QueueTicket.SERVING,
    ).select_related("booking", "booking__service", "assigned_counter")


def get_people_ahead(ticket):
    """Count same-lane waiting-ahead plus customers currently served from that lane."""
    if ticket.status == QueueTicket.SERVING:
        return 0

    return _waiting_ahead_queryset(ticket).count() + _serving_same_lane_queryset(ticket).count()


def get_queue_position(ticket):
    if ticket.status == QueueTicket.SERVING:
        return 0
    return get_people_ahead(ticket) + 1


def _eligible_counter_types(queue_type):
    if queue_type == QueueTicket.GENERAL:
        return {QueueTicket.GENERAL, QueueTicket.PRIORITY}
    return {QueueTicket.PRIORITY}


def _priority_waiting_queryset(ticket):
    """Priority work currently competing for a flexible Priority counter."""
    return QueueTicket.objects.filter(
        booking__branch=ticket.booking.branch,
        booking__booking_date=ticket.booking.booking_date,
        booking__checked_in_at__isnull=False,
        queue_type=QueueTicket.PRIORITY,
        status=QueueTicket.WAITING,
        assigned_counter__isnull=True,
    ).select_related("booking", "booking__service").order_by("booking__checked_in_at", "id")


def calculate_estimated_wait_seconds(ticket, now=None):
    """
    Estimate when this waiting customer can start service under Smart Q routing.

    General counters serve only General customers. Priority counters are now
    work-conserving: Priority is always served first, but an idle Priority counter
    may help General. The ETA therefore models each physical counter separately
    and, for a General customer, lets current Priority work consume the shared
    counter before assigning General work to it.
    """
    if ticket.status == QueueTicket.SERVING:
        return 0
    if ticket.booking.checked_in_at is None:
        return 0
    if now is None:
        now = timezone.now()

    eligible_types = _eligible_counter_types(ticket.queue_type)
    counters = list(
        Counter.objects.filter(
            branch=ticket.booking.branch,
            queue_type__in=eligible_types,
            status=Counter.OPEN,
        ).order_by("counter_number", "id")
    )
    counter_states = {
        counter.id: {"type": counter.queue_type, "available": 0}
        for counter in counters
    }

    serving = list(
        QueueTicket.objects.filter(
            booking__branch=ticket.booking.branch,
            booking__booking_date=ticket.booking.booking_date,
            status=QueueTicket.SERVING,
            assigned_counter__queue_type__in=eligible_types,
        ).select_related("booking", "booking__service", "assigned_counter")
    )
    for serving_ticket in serving:
        counter = serving_ticket.assigned_counter
        if counter is None:
            continue
        if counter.id not in counter_states:
            counter_states[counter.id] = {
                "type": counter.queue_type,
                "available": 0,
            }
        counter_states[counter.id]["available"] = max(
            counter_states[counter.id]["available"],
            get_service_clock(serving_ticket, now=now)["service_remaining_seconds"],
        )

    if not counter_states:
        # Preserve the historical deterministic fallback before counters open.
        virtual_type = (
            QueueTicket.PRIORITY
            if ticket.queue_type == QueueTicket.PRIORITY
            else QueueTicket.GENERAL
        )
        counter_states["virtual-0"] = {"type": virtual_type, "available": 0}

    same_lane_ahead = list(_waiting_ahead_queryset(ticket))
    if ticket.queue_type == QueueTicket.PRIORITY:
        priority_work = list(same_lane_ahead)
        general_work = []
    else:
        priority_work = list(_priority_waiting_queryset(ticket))
        general_work = list(same_lane_ahead)

    # Simulate dispatch until one eligible counter can accept the target ticket.
    # Priority counters always consume pending Priority work before General work.
    safety = len(priority_work) + len(general_work) + len(counter_states) + 10
    for _ in range(max(safety, 1) * 3):
        counter_id = min(
            counter_states,
            key=lambda key: (counter_states[key]["available"], str(key)),
        )
        state = counter_states[counter_id]

        if state["type"] == QueueTicket.PRIORITY and priority_work:
            work = priority_work.pop(0)
            state["available"] += _service_target_seconds(work)
            continue

        if ticket.queue_type == QueueTicket.PRIORITY:
            # No priority customer remains ahead; this Priority counter can call target.
            return max(int(state["available"]), 0)

        if general_work:
            work = general_work.pop(0)
            state["available"] += _service_target_seconds(work)
            continue

        # For a General target, either a General counter is free or a Priority
        # counter has no remaining Priority work and can overflow to General.
        return max(int(state["available"]), 0)

    # Defensive fallback should never be reached, but remains finite.
    return max(min(state["available"] for state in counter_states.values()), 0)


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

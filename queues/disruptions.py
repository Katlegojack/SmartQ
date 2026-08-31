from django.db import transaction
from django.utils import timezone

from .models import QueueDisruptionImpact, QueuePause, QueueTicket


def pause_queue(branch, service, booking_date, reason=""):
    """Create or reuse one active service pause for a branch/service/date."""
    active_pause = QueuePause.objects.filter(
        branch=branch,
        service=service,
        booking_date=booking_date,
        is_active=True,
    ).first()

    if active_pause is not None:
        return active_pause

    return QueuePause.objects.create(
        branch=branch,
        service=service,
        booking_date=booking_date,
        reason=reason,
        is_active=True,
    )


def resume_queue(queue_pause):
    """Close a pause once; repeated resume calls are harmless."""
    if queue_pause is None:
        return None
    if not queue_pause.is_active:
        return queue_pause

    queue_pause.ended_at = timezone.now()
    queue_pause.is_active = False
    queue_pause.save(update_fields=["ended_at", "is_active"])
    return queue_pause


def get_pause_duration_minutes(queue_pause):
    """Return elapsed pause minutes using now while a pause is still active."""
    if queue_pause is None:
        return 0

    end_time = queue_pause.ended_at
    if queue_pause.is_active or end_time is None:
        end_time = timezone.now()

    duration = end_time - queue_pause.started_at
    return max(round(duration.total_seconds() / 60), 0)


def calculate_lost_service_capacity(queue_pause):
    """
    Approximate how many whole customer service opportunities the pause consumed.

    Smart Q currently has no per-service counter assignment, so this deliberately
    uses the approved service-duration approximation rather than inventing a
    multiplier from counters that are not mapped to a specific service.
    """
    if queue_pause is None:
        return 0

    average_service_time = queue_pause.service.average_service_time
    if not average_service_time or average_service_time <= 0:
        return 0

    pause_duration = get_pause_duration_minutes(queue_pause)
    return max(round(pause_duration / average_service_time), 0)


def get_pause_impact_summary(queue_pause):
    """Return the operational facts used by manager disruption screens."""
    if queue_pause is None:
        return {
            "duration_minutes": 0,
            "lost_service_capacity": 0,
            "is_active": False,
        }

    return {
        "id": queue_pause.id,
        "branch_id": queue_pause.branch_id,
        "branch": str(queue_pause.branch),
        "service_id": queue_pause.service_id,
        "service": str(queue_pause.service),
        "booking_date": queue_pause.booking_date,
        "started_at": queue_pause.started_at,
        "ended_at": queue_pause.ended_at,
        "reason": queue_pause.reason,
        "is_active": queue_pause.is_active,
        "duration_minutes": get_pause_duration_minutes(queue_pause),
        "lost_service_capacity": calculate_lost_service_capacity(queue_pause),
    }


def get_affected_waiting_tickets(queue_pause):
    """Return WAITING tickets in exactly the paused branch/service/date scope."""
    if queue_pause is None:
        return QueueTicket.objects.none()

    return (
        QueueTicket.objects.filter(
            booking__branch=queue_pause.branch,
            booking__service=queue_pause.service,
            booking__booking_date=queue_pause.booking_date,
            status=QueueTicket.WAITING,
        )
        .select_related("booking", "booking__user", "booking__guest_customer")
        .order_by("created_at", "id")
    )


def get_reschedule_risk_tickets(queue_pause):
    """Select the tail of the affected queue according to lost service capacity."""
    if queue_pause is None:
        return []

    lost_capacity = calculate_lost_service_capacity(queue_pause)
    if lost_capacity <= 0:
        return []

    affected_tickets = list(get_affected_waiting_tickets(queue_pause))
    if lost_capacity >= len(affected_tickets):
        return affected_tickets

    # Customers furthest back are most likely to fall outside the recovered
    # service capacity after the disruption ends.
    return affected_tickets[-lost_capacity:]


def get_disruption_report(queue_pause):
    """Return one manager-readable snapshot of a disruption's current impact."""
    affected_tickets = list(get_affected_waiting_tickets(queue_pause))
    risk_tickets = get_reschedule_risk_tickets(queue_pause)

    return {
        "pause_impact": get_pause_impact_summary(queue_pause),
        "affected_waiting_count": len(affected_tickets),
        "reschedule_risk_count": len(risk_tickets),
        "reschedule_risk_tickets": [
            ticket.queue_number for ticket in risk_tickets
        ],
    }


@transaction.atomic
def create_disruption_impact_records(queue_pause):
    """
    Persist affected/risk snapshots idempotently for a finished or active pause.

    `get_or_create` works with QueueDisruptionImpact's uniqueness constraint, so
    retrying this operation cannot duplicate the same pause/ticket/impact type.
    """
    if queue_pause is None:
        return {
            "affected_processed": 0,
            "affected_created": 0,
            "reschedule_risk_processed": 0,
            "reschedule_risk_created": 0,
        }

    affected_tickets = list(get_affected_waiting_tickets(queue_pause))
    risk_tickets = get_reschedule_risk_tickets(queue_pause)

    affected_created = 0
    for ticket in affected_tickets:
        _, created = QueueDisruptionImpact.objects.get_or_create(
            queue_pause=queue_pause,
            ticket=ticket,
            impact_type=QueueDisruptionImpact.AFFECTED,
            defaults={
                "message": "Your queue was affected by a service disruption."
            },
        )
        if created:
            affected_created += 1

    risk_created = 0
    for ticket in risk_tickets:
        _, created = QueueDisruptionImpact.objects.get_or_create(
            queue_pause=queue_pause,
            ticket=ticket,
            impact_type=QueueDisruptionImpact.RESCHEDULE_RISK,
            defaults={
                "message": (
                    "You may need to be rescheduled due to a service disruption."
                )
            },
        )
        if created:
            risk_created += 1

    return {
        "affected_processed": len(affected_tickets),
        "affected_created": affected_created,
        "reschedule_risk_processed": len(risk_tickets),
        "reschedule_risk_created": risk_created,
    }


def get_unnotified_disruption_impact(queue_pause=None):
    """Return unnotified impacts globally or, when supplied, for one pause."""
    impacts = QueueDisruptionImpact.objects.filter(is_notified=False)
    if queue_pause is not None:
        impacts = impacts.filter(queue_pause=queue_pause)

    return impacts.select_related("ticket", "ticket__booking").order_by("created_at", "id")


def mark_disruption_impact_notified(impact):
    """Mark an impact as delivered to the available notification channel."""
    if impact is None:
        return None

    impact.is_notified = True
    impact.save(update_fields=["is_notified"])
    return impact

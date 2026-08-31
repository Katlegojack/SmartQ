from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from bookings.models import Booking
from notifications.services import create_reschedule_applied_notification
from queues.models import QueueDisruptionImpact, QueueTicket
from services.availability import validate_booking_slot

from .models import RescheduleOption, RescheduleRecommendation
from .slots import get_available_reschedule_slots


DEFAULT_REASON = (
    "Customer was at risk of not being served because service capacity was lost "
    "during a queue disruption."
)


def get_reschedule_risk_impacts(queue_pause=None):
    """Return reschedule-risk impacts globally or for one specific pause."""
    impacts = QueueDisruptionImpact.objects.filter(
        impact_type=QueueDisruptionImpact.RESCHEDULE_RISK
    ).select_related("ticket", "ticket__booking", "queue_pause")

    if queue_pause is not None:
        impacts = impacts.filter(queue_pause=queue_pause)

    return impacts.order_by("created_at", "id")


@transaction.atomic
def create_reschedule_recommendation_for_impact(
    impact,
    *,
    reason="",
    max_slots=5,
):
    """
    Create one recommendation and up to five current capacity-safe options.

    A QueueDisruptionImpact has at most one recommendation by schema. Re-running
    this function refreshes options instead of duplicating recommendations.
    """
    if impact is None or impact.impact_type != QueueDisruptionImpact.RESCHEDULE_RISK:
        return {"recommendation": None, "created": False, "options_created": 0}

    ticket = impact.ticket
    if ticket is None or ticket.booking_id is None:
        return {"recommendation": None, "created": False, "options_created": 0}

    booking = ticket.booking
    available_slots = get_available_reschedule_slots(
        booking,
        start_date=booking.booking_date + timedelta(days=1),
        max_slots=max_slots,
    )
    if not available_slots:
        return {"recommendation": None, "created": False, "options_created": 0}

    first_slot = available_slots[0]
    recommendation, created = RescheduleRecommendation.objects.get_or_create(
        disruption_impact=impact,
        defaults={
            "booking": booking,
            "ticket": ticket,
            "old_booking_date": booking.booking_date,
            "old_booking_time": booking.booking_time,
            "suggested_booking_date": first_slot["date"],
            "suggested_booking_time": first_slot["time"],
            "priority_on_reschedule": True,
            "reason": reason or DEFAULT_REASON,
            "status": RescheduleRecommendation.PENDING,
        },
    )

    # Pending recommendations may be refreshed because slot capacity changes over
    # time. Once a manager/customer has approved/applied/rejected a recommendation,
    # preserve the audit snapshot rather than silently rewriting its options.
    if recommendation.status == RescheduleRecommendation.PENDING:
        recommendation.booking = booking
        recommendation.ticket = ticket
        recommendation.reason = reason or recommendation.reason or DEFAULT_REASON
        recommendation.priority_on_reschedule = True
        recommendation.suggested_booking_date = first_slot["date"]
        recommendation.suggested_booking_time = first_slot["time"]
        recommendation.save(
            update_fields=[
                "booking",
                "ticket",
                "reason",
                "priority_on_reschedule",
                "suggested_booking_date",
                "suggested_booking_time",
                "updated_at",
            ]
        )

        RescheduleOption.objects.filter(recommendation=recommendation).delete()
        RescheduleOption.objects.bulk_create(
            [
                RescheduleOption(
                    recommendation=recommendation,
                    option_date=slot["date"],
                    option_time=slot["time"],
                    capacity=slot["capacity"],
                    booked_count=slot["booked_count"],
                    available_count=slot["available_count"],
                    is_recommended=slot["is_recommended"],
                )
                for slot in available_slots
            ]
        )

    return {
        "recommendation": recommendation,
        "created": created,
        "options_created": len(available_slots) if recommendation.status == RescheduleRecommendation.PENDING else 0,
    }


def create_reschedule_recommendations_for_risk_impacts(queue_pause=None, *, max_slots=5):
    """Create/refresh recommendations for every persisted reschedule-risk impact."""
    processed = 0
    created = 0
    options_created = 0

    for impact in get_reschedule_risk_impacts(queue_pause):
        processed += 1
        result = create_reschedule_recommendation_for_impact(
            impact,
            max_slots=max_slots,
        )
        if result["created"]:
            created += 1
        options_created += result["options_created"]

    return {
        "recommendations_processed": processed,
        "recommendations_created": created,
        "options_created": options_created,
    }


def get_selected_reschedule_option(recommendation):
    """Return the single selected option, if one has been chosen."""
    if recommendation is None:
        return None
    return RescheduleOption.objects.filter(
        recommendation=recommendation,
        is_selected=True,
    ).first()


@transaction.atomic
def select_reschedule_option(option):
    """Select one still-available option and approve its recommendation."""
    if option is None:
        return None, "missing_option"

    option = (
        RescheduleOption.objects.select_for_update()
        .select_related("recommendation", "recommendation__booking")
        .filter(pk=option.pk)
        .first()
    )
    if option is None:
        return None, "missing_option"

    recommendation = option.recommendation
    if recommendation.status not in [
        RescheduleRecommendation.PENDING,
        RescheduleRecommendation.APPROVED,
    ]:
        return None, "recommendation_finalized"

    booking = recommendation.booking
    _, error_code = validate_booking_slot(
        booking.branch,
        booking.service,
        option.option_date,
        option.option_time,
        exclude_booking=booking,
        lock=True,
    )
    if error_code:
        return None, error_code

    RescheduleOption.objects.filter(recommendation=recommendation).update(
        is_selected=False
    )
    option.is_selected = True
    option.save(update_fields=["is_selected"])

    recommendation.suggested_booking_date = option.option_date
    recommendation.suggested_booking_time = option.option_time
    recommendation.status = RescheduleRecommendation.APPROVED
    recommendation.save(
        update_fields=[
            "suggested_booking_date",
            "suggested_booking_time",
            "status",
            "updated_at",
        ]
    )
    return option, None


@transaction.atomic
def apply_approved_reschedule(recommendation):
    """
    Atomically move an approved disrupted booking to its selected future slot.

    The booking returns to SCHEDULED/PENDING and must check in again. The ticket
    is marked Priority as disruption compensation, but it is not put in WAITING
    before check-in because that would violate Smart Q's live-queue activation rule.
    """
    if recommendation is None:
        return None, "missing_recommendation"

    recommendation = (
        RescheduleRecommendation.objects.select_for_update()
        .select_related("booking", "ticket")
        .filter(pk=recommendation.pk)
        .first()
    )
    if recommendation is None:
        return None, "missing_recommendation"

    if recommendation.status == RescheduleRecommendation.APPLIED:
        return recommendation, None
    if recommendation.status != RescheduleRecommendation.APPROVED:
        return None, "not_approved"

    selected_option = get_selected_reschedule_option(recommendation)
    if selected_option is None:
        return None, "missing_selection"

    booking = Booking.objects.select_for_update().get(pk=recommendation.booking_id)
    _, error_code = validate_booking_slot(
        booking.branch,
        booking.service,
        selected_option.option_date,
        selected_option.option_time,
        exclude_booking=booking,
        lock=True,
    )
    if error_code:
        return None, error_code

    ticket = recommendation.ticket
    if ticket is None:
        ticket = QueueTicket.objects.select_for_update().filter(booking=booking).first()
    else:
        ticket = QueueTicket.objects.select_for_update().get(pk=ticket.pk)
    if ticket is None:
        return None, "missing_ticket"

    booking.booking_date = selected_option.option_date
    booking.booking_time = selected_option.option_time
    booking.checked_in_at = None
    booking.status = Booking.PENDING
    booking.save(
        update_fields=["booking_date", "booking_time", "checked_in_at", "status"]
    )

    ticket.queue_type = (
        QueueTicket.PRIORITY
        if recommendation.priority_on_reschedule
        else ticket.queue_type
    )
    ticket.status = QueueTicket.SCHEDULED
    ticket.assigned_counter = None
    ticket.save(update_fields=["queue_type", "status", "assigned_counter"])

    recommendation.ticket = ticket
    recommendation.suggested_booking_date = selected_option.option_date
    recommendation.suggested_booking_time = selected_option.option_time
    recommendation.status = RescheduleRecommendation.APPLIED
    recommendation.applied_at = timezone.now()
    recommendation.save(
        update_fields=[
            "ticket",
            "suggested_booking_date",
            "suggested_booking_time",
            "status",
            "applied_at",
            "updated_at",
        ]
    )

    create_reschedule_applied_notification(recommendation)
    return recommendation, None

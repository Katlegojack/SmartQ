from django.db.models.signals import post_save
from django.dispatch import receiver

from .forecasting import (
    capture_queue_entry_observation,
    record_call_outcome,
    record_service_outcome,
)
from .models import QueueEvent


@receiver(post_save, sender=QueueEvent)
def capture_forecasting_observation(sender, instance, created, **kwargs):
    """
    Build modelling observations from the same append-only events used by audit.

    Every live-entry path records CHECKED_IN, every service start records CALLED,
    and every successful service records COMPLETED. Subscribing here keeps the
    forecasting dataset consistent across Customer, Reception and Counter flows.
    """
    if not created or instance.ticket_id is None:
        return

    ticket = instance.ticket

    if instance.event_type == QueueEvent.CHECKED_IN:
        capture_queue_entry_observation(ticket, now=instance.occurred_at)
        return

    if instance.event_type == QueueEvent.CALLED:
        target = instance.metadata.get("service_target_seconds")
        if target is None:
            target = ticket.service_target_seconds or 0
        record_call_outcome(
            ticket,
            called_at=instance.occurred_at,
            service_target_seconds=target,
        )
        return

    if instance.event_type == QueueEvent.COMPLETED:
        actual = instance.metadata.get("actual_service_seconds")
        if actual is None:
            actual = ticket.actual_service_seconds
        variance = instance.metadata.get("service_variance_seconds")
        if variance is None:
            variance = ticket.service_variance_seconds
        if actual is None or variance is None:
            return
        record_service_outcome(
            ticket,
            completed_at=instance.occurred_at,
            actual_service_seconds=actual,
            service_variance_seconds=variance,
        )

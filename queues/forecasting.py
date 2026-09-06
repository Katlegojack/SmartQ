from datetime import datetime, time, timedelta

from django.utils import timezone

from counters.models import Counter

from .models import QueueForecastObservation, QueueTicket
from .waiting_time import get_ticket_prediction


FORECAST_EXPORT_FIELDS = [
    "observation_id",
    "ticket_id",
    "branch_id",
    "service_id",
    "queue_type",
    "booking_source",
    "checked_in_at",
    "checked_in_weekday",
    "checked_in_hour",
    "people_ahead",
    "open_counter_count",
    "serving_count",
    "baseline_estimated_wait_seconds",
    "actual_wait_seconds",
    "wait_variance_seconds",
    "service_target_seconds",
    "actual_service_seconds",
    "service_variance_seconds",
]


def capture_queue_entry_observation(ticket, *, now=None):
    """Capture only information that is known when a customer enters the live queue."""
    if now is None:
        now = timezone.now()

    ticket = QueueTicket.objects.select_related(
        "booking", "booking__branch", "booking__service"
    ).get(pk=ticket.pk)
    booking = ticket.booking

    open_counter_count = Counter.objects.filter(
        branch=booking.branch,
        queue_type=ticket.queue_type,
        status=Counter.OPEN,
    ).count()
    serving_count = QueueTicket.objects.filter(
        booking__branch=booking.branch,
        booking__booking_date=booking.booking_date,
        queue_type=ticket.queue_type,
        status=QueueTicket.SERVING,
    ).count()
    prediction = get_ticket_prediction(ticket, now=now)

    return QueueForecastObservation.objects.create(
        ticket=ticket,
        branch=booking.branch,
        service=booking.service,
        queue_type=ticket.queue_type,
        booking_source=booking.source,
        checked_in_at=now,
        baseline_estimated_wait_seconds=prediction["estimated_wait_seconds"],
        people_ahead=prediction["people_ahead"],
        open_counter_count=open_counter_count,
        serving_count=serving_count,
    )


def _latest_open_observation(ticket):
    return (
        QueueForecastObservation.objects.filter(
            ticket=ticket,
            called_at__isnull=True,
        )
        .order_by("-checked_in_at", "-id")
        .first()
    )


def record_call_outcome(ticket, *, called_at, service_target_seconds):
    """Attach the actual wait label to the most recent queue-entry observation."""
    observation = _latest_open_observation(ticket)
    if observation is None:
        return None

    actual_wait_seconds = max(
        int(round((called_at - observation.checked_in_at).total_seconds())),
        0,
    )
    baseline = observation.baseline_estimated_wait_seconds

    observation.called_at = called_at
    observation.actual_wait_seconds = actual_wait_seconds
    observation.wait_variance_seconds = (
        actual_wait_seconds - baseline if baseline is not None else None
    )
    observation.service_target_seconds = max(int(service_target_seconds), 0)
    observation.save(
        update_fields=[
            "called_at",
            "actual_wait_seconds",
            "wait_variance_seconds",
            "service_target_seconds",
        ]
    )
    return observation


def record_service_outcome(
    ticket,
    *,
    completed_at,
    actual_service_seconds,
    service_variance_seconds,
):
    """Attach the final service-duration label to the active observation."""
    observation = (
        QueueForecastObservation.objects.filter(
            ticket=ticket,
            called_at__isnull=False,
            service_completed_at__isnull=True,
        )
        .order_by("-called_at", "-id")
        .first()
    )
    if observation is None:
        return None

    observation.service_completed_at = completed_at
    observation.actual_service_seconds = max(int(actual_service_seconds), 0)
    observation.service_variance_seconds = int(service_variance_seconds)
    observation.save(
        update_fields=[
            "service_completed_at",
            "actual_service_seconds",
            "service_variance_seconds",
        ]
    )
    return observation


def forecasting_queryset(*, branch=None, start_date=None, end_date=None):
    queryset = QueueForecastObservation.objects.select_related(
        "branch", "service", "ticket"
    ).order_by("checked_in_at", "id")

    if branch is not None:
        queryset = queryset.filter(branch=branch)
    if start_date is not None:
        start = timezone.make_aware(
            datetime.combine(start_date, time.min),
            timezone.get_current_timezone(),
        )
        queryset = queryset.filter(checked_in_at__gte=start)
    if end_date is not None:
        end = timezone.make_aware(
            datetime.combine(end_date + timedelta(days=1), time.min),
            timezone.get_current_timezone(),
        )
        queryset = queryset.filter(checked_in_at__lt=end)
    return queryset


def observation_to_training_row(observation):
    """
    Return a modelling row containing operational features and labels, not PII.

    Protected/sensitive customer attributes are deliberately absent. Queue type is
    retained because it is an operational queue lane produced by Smart Q's policy,
    but the underlying age/disability/pregnancy attributes are not exported here.
    """
    local_check_in = timezone.localtime(observation.checked_in_at)
    return {
        "observation_id": observation.id,
        "ticket_id": observation.ticket_id,
        "branch_id": observation.branch_id,
        "service_id": observation.service_id,
        "queue_type": observation.queue_type,
        "booking_source": observation.booking_source,
        "checked_in_at": local_check_in.isoformat(),
        "checked_in_weekday": local_check_in.weekday(),
        "checked_in_hour": local_check_in.hour,
        "people_ahead": observation.people_ahead,
        "open_counter_count": observation.open_counter_count,
        "serving_count": observation.serving_count,
        "baseline_estimated_wait_seconds": observation.baseline_estimated_wait_seconds,
        "actual_wait_seconds": observation.actual_wait_seconds,
        "wait_variance_seconds": observation.wait_variance_seconds,
        "service_target_seconds": observation.service_target_seconds,
        "actual_service_seconds": observation.actual_service_seconds,
        "service_variance_seconds": observation.service_variance_seconds,
    }


def iter_forecasting_rows(*, branch=None, start_date=None, end_date=None):
    for observation in forecasting_queryset(
        branch=branch,
        start_date=start_date,
        end_date=end_date,
    ):
        yield observation_to_training_row(observation)


def _mean_minutes(values, *, absolute=False):
    values = [value for value in values if value is not None]
    if not values:
        return None
    if absolute:
        values = [abs(value) for value in values]
    return round(sum(values) / len(values) / 60, 2)


def build_forecasting_summary(branch, start_date, end_date):
    observations = list(
        forecasting_queryset(
            branch=branch,
            start_date=start_date,
            end_date=end_date,
        )
    )
    wait_errors = [
        item.wait_variance_seconds
        for item in observations
        if item.actual_wait_seconds is not None
        and item.baseline_estimated_wait_seconds is not None
        and item.wait_variance_seconds is not None
    ]
    service_errors = [
        item.service_variance_seconds
        for item in observations
        if item.actual_service_seconds is not None
        and item.service_target_seconds is not None
        and item.service_variance_seconds is not None
    ]

    return {
        "branch_id": branch.id,
        "branch_name": branch.name,
        "period": {
            "start_date": start_date,
            "end_date": end_date,
        },
        "model_status": "data_collection",
        "machine_learning_enabled": False,
        "observations": len(observations),
        "wait_labels": sum(item.actual_wait_seconds is not None for item in observations),
        "service_labels": sum(item.actual_service_seconds is not None for item in observations),
        "baseline_wait_mae_minutes": _mean_minutes(wait_errors, absolute=True),
        "baseline_wait_bias_minutes": _mean_minutes(wait_errors),
        "service_target_mae_minutes": _mean_minutes(service_errors, absolute=True),
        "service_target_bias_minutes": _mean_minutes(service_errors),
    }

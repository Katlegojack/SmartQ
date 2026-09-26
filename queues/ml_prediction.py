from datetime import timedelta
from functools import lru_cache
from pathlib import Path

import joblib
import pandas as pd
from django.conf import settings
from django.utils import timezone

from bookings.models import Booking
from counters.models import Counter

from .eligibility import get_booking_datetime, get_service_eligible_at
from .models import QueueForecastObservation, QueueTicket


MODEL_PATH = (
    Path(settings.BASE_DIR)
    / "machine_learning"
    / "runtime"
    / "smartq_wait_time_model.joblib"
)

REQUIRED_FEATURES = [
    "arrival_offset_minutes",
    "people_ahead",
    "general_waiting",
    "priority_waiting",
    "serving_count",
    "open_general_counters",
    "open_priority_counters",
    "effective_open_counters",
    "counter_utilisation",
    "queue_pressure_index",
    "workload_minutes_ahead",
    "recent_avg_service_minutes_10",
    "recent_avg_wait_minutes_10",
    "recent_throughput_60m",
    "service_target_minutes",
    "hour_of_day",
    "branch_code",
    "service_code",
    "booking_source",
    "queue_type",
    "day_of_week",
    "is_peak_period",
]


def ml_runtime_available():
    return bool(
        getattr(settings, "SMARTQ_ML_ENABLED", True)
        and MODEL_PATH.exists()
    )


@lru_cache(maxsize=1)
def load_wait_model_bundle():
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"SmartQ ML model not found at {MODEL_PATH}")
    return joblib.load(MODEL_PATH)


def _service_target_minutes(ticket):
    return float(ticket.booking.service.average_service_time or 0)


def _waiting_tickets(branch, booking_date):
    return QueueTicket.objects.filter(
        booking__branch=branch,
        booking__booking_date=booking_date,
        booking__checked_in_at__isnull=False,
        status=QueueTicket.WAITING,
        assigned_counter__isnull=True,
    ).select_related("booking", "booking__service")


def _same_lane_waiting_ahead(ticket):
    current_eligible = get_service_eligible_at(ticket.booking)
    if current_eligible is None:
        return []

    current_key = (current_eligible, ticket.booking.checked_in_at, ticket.pk)
    candidates = []
    for other in _waiting_tickets(ticket.booking.branch, ticket.booking.booking_date):
        if other.pk == ticket.pk or other.queue_type != ticket.queue_type:
            continue
        eligible_at = get_service_eligible_at(other.booking)
        if eligible_at is None:
            continue
        key = (eligible_at, other.booking.checked_in_at, other.pk)
        if key < current_key:
            candidates.append(other)

    return sorted(
        candidates,
        key=lambda item: (
            get_service_eligible_at(item.booking),
            item.booking.checked_in_at,
            item.pk,
        ),
    )


def _recent_history(branch, now):
    recent = QueueForecastObservation.objects.filter(
        branch=branch,
        checked_in_at__lt=now,
    )
    service_values = list(
        recent.filter(
            service_completed_at__isnull=False,
            actual_service_seconds__isnull=False,
        )
        .order_by("-service_completed_at", "-id")
        .values_list("actual_service_seconds", flat=True)[:10]
    )
    wait_values = list(
        recent.filter(
            called_at__isnull=False,
            actual_wait_seconds__isnull=False,
        )
        .order_by("-called_at", "-id")
        .values_list("actual_wait_seconds", flat=True)[:10]
    )
    one_hour_ago = now - timedelta(hours=1)
    throughput = recent.filter(
        service_completed_at__gte=one_hour_ago,
        service_completed_at__lt=now,
    ).count()

    avg_service = sum(service_values) / len(service_values) / 60 if service_values else None
    avg_wait = sum(wait_values) / len(wait_values) / 60 if wait_values else None
    return avg_service, avg_wait, float(throughput)


def build_live_ml_features(ticket, *, now=None):
    """Build the exact 22-column input contract expected by the trained wait model."""
    if now is None:
        now = timezone.now()

    ticket = QueueTicket.objects.select_related(
        "booking", "booking__branch", "booking__service"
    ).get(pk=ticket.pk)
    booking = ticket.booking
    branch = booking.branch
    booking_date = booking.booking_date

    waiting = list(_waiting_tickets(branch, booking_date))
    general_waiting = sum(
        item.pk != ticket.pk and item.queue_type == QueueTicket.GENERAL
        for item in waiting
    )
    priority_waiting = sum(
        item.pk != ticket.pk and item.queue_type == QueueTicket.PRIORITY
        for item in waiting
    )

    serving = list(
        QueueTicket.objects.filter(
            booking__branch=branch,
            booking__booking_date=booking_date,
            status=QueueTicket.SERVING,
        ).select_related("booking", "booking__service")
    )
    serving_count = len(serving)

    open_general = Counter.objects.filter(
        branch=branch,
        queue_type=QueueTicket.GENERAL,
        status=Counter.OPEN,
    ).count()
    open_priority = Counter.objects.filter(
        branch=branch,
        queue_type=QueueTicket.PRIORITY,
        status=Counter.OPEN,
    ).count()
    total_open = open_general + open_priority
    effective_open = open_general if ticket.queue_type == QueueTicket.GENERAL else open_priority

    counter_utilisation = serving_count / total_open if total_open else 0.0
    queue_pressure = (
        (general_waiting + priority_waiting + serving_count) / total_open
        if total_open
        else float(general_waiting + priority_waiting + serving_count)
    )

    ahead = _same_lane_waiting_ahead(ticket)
    workload_seconds = 0
    for serving_ticket in serving:
        if serving_ticket.queue_type != ticket.queue_type:
            continue
        target = serving_ticket.service_target_seconds
        if target is None:
            target = int(round(_service_target_minutes(serving_ticket) * 60))
        started = serving_ticket.service_started_at
        if started is None:
            remaining = target
        else:
            elapsed = max(int((now - started).total_seconds()), 0)
            remaining = max(target - elapsed, 0)
        workload_seconds += remaining

    for ahead_ticket in ahead:
        workload_seconds += int(round(_service_target_minutes(ahead_ticket) * 60))

    avg_service, avg_wait, throughput = _recent_history(branch, now)
    checked_in = booking.checked_in_at or now
    local_check_in = timezone.localtime(checked_in)

    if booking.source == Booking.WALK_IN:
        arrival_offset = 0.0
        booking_source = "WALK_IN"
    else:
        appointment_at = get_booking_datetime(booking)
        arrival_offset = (checked_in - appointment_at).total_seconds() / 60
        booking_source = "APPOINTMENT"

    minute_of_day = local_check_in.hour * 60 + local_check_in.minute
    is_peak = (
        9 * 60 <= minute_of_day <= 11 * 60 + 30
        or 13 * 60 <= minute_of_day <= 15 * 60 + 30
    )

    features = {
        "arrival_offset_minutes": float(round(arrival_offset, 3)),
        "people_ahead": float(len(ahead)),
        "general_waiting": float(general_waiting),
        "priority_waiting": float(priority_waiting),
        "serving_count": float(serving_count),
        "open_general_counters": float(open_general),
        "open_priority_counters": float(open_priority),
        "effective_open_counters": float(effective_open),
        "counter_utilisation": float(counter_utilisation),
        "queue_pressure_index": float(queue_pressure),
        "workload_minutes_ahead": float(workload_seconds / 60),
        "recent_avg_service_minutes_10": avg_service,
        "recent_avg_wait_minutes_10": avg_wait,
        "recent_throughput_60m": throughput,
        "service_target_minutes": _service_target_minutes(ticket),
        "hour_of_day": float(local_check_in.hour),
        "branch_code": branch.branch_code,
        "service_code": booking.service.service_code,
        "booking_source": booking_source,
        "queue_type": ticket.queue_type.upper(),
        "day_of_week": local_check_in.strftime("%A"),
        "is_peak_period": bool(is_peak),
    }

    missing = [name for name in REQUIRED_FEATURES if name not in features]
    if missing:
        raise ValueError(f"Missing SmartQ ML features: {', '.join(missing)}")
    return features


def predict_wait_minutes(ticket, *, now=None):
    """Return an ML wait estimate in minutes, or None when ML is disabled."""
    if not getattr(settings, "SMARTQ_ML_ENABLED", True):
        return None

    features = build_live_ml_features(ticket, now=now)
    bundle = load_wait_model_bundle()
    expected = bundle.get("features") or REQUIRED_FEATURES
    missing = [name for name in expected if name not in features]
    if missing:
        raise ValueError(f"Missing model inputs: {', '.join(missing)}")

    row = pd.DataFrame([{name: features[name] for name in expected}])
    transformed = bundle["preprocessor"].transform(row)
    raw = float(bundle["model"].predict(transformed)[0])
    return max(0.0, raw)

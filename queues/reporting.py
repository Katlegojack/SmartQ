from collections import defaultdict
from datetime import datetime, time, timedelta

from django.utils import timezone

from .models import QueueEvent


REPORT_EVENT_TYPES = {
    QueueEvent.CHECKED_IN,
    QueueEvent.CALLED,
    QueueEvent.COMPLETED,
    QueueEvent.NO_SHOW,
    QueueEvent.CANCELLED,
    QueueEvent.RESCHEDULED,
    QueueEvent.DISRUPTION_RESCHEDULED,
}


def _aware_day_start(day):
    value = datetime.combine(day, time.min)
    return timezone.make_aware(value, timezone.get_current_timezone())


def _aware_day_end_exclusive(day):
    return _aware_day_start(day + timedelta(days=1))


def _round_minutes(seconds_values):
    if not seconds_values:
        return None
    return round(sum(seconds_values) / len(seconds_values) / 60, 2)


def build_branch_operational_report(branch, start_date, end_date):
    """
    Build one historical operational report from the append-only QueueEvent log.

    The report intentionally reads QueueEvent as the historical source of truth.
    It does not alter or replace Smart Q's approved live ETA formula.
    """
    events = list(
        QueueEvent.objects.filter(
            branch=branch,
            occurred_at__gte=_aware_day_start(start_date),
            occurred_at__lt=_aware_day_end_exclusive(end_date),
            event_type__in=REPORT_EVENT_TYPES,
        )
        .values(
            "id",
            "event_type",
            "ticket_id",
            "booking_id",
            "service_id",
            "service__name",
            "queue_type",
            "source",
            "occurred_at",
        )
        .order_by("occurred_at", "id")
    )

    summary = {
        "events": len(events),
        "checked_in": 0,
        "called": 0,
        "completed": 0,
        "no_show": 0,
        "cancelled": 0,
        "rescheduled": 0,
        "disruption_rescheduled": 0,
    }
    daily = defaultdict(
        lambda: {
            "checked_in": 0,
            "called": 0,
            "completed": 0,
            "no_show": 0,
            "cancelled": 0,
        }
    )
    services = defaultdict(
        lambda: {
            "service_id": None,
            "service_name": "Unknown service",
            "checked_in": 0,
            "completed": 0,
            "no_show": 0,
            "cancelled": 0,
        }
    )
    queue_types = defaultdict(int)
    sources = defaultdict(int)

    ticket_times = defaultdict(dict)
    booking_times = defaultdict(dict)

    for event in events:
        event_type = event["event_type"]
        occurred_at = event["occurred_at"]
        summary[event_type] += 1

        day_key = timezone.localtime(occurred_at).date().isoformat()
        if event_type in daily[day_key]:
            daily[day_key][event_type] += 1

        service_id = event["service_id"]
        service_key = str(service_id) if service_id is not None else "unknown"
        service_entry = services[service_key]
        service_entry["service_id"] = service_id
        service_entry["service_name"] = event["service__name"] or "Unknown service"
        if event_type in service_entry:
            service_entry[event_type] += 1

        if event_type == QueueEvent.CHECKED_IN:
            if event["queue_type"]:
                queue_types[event["queue_type"]] += 1
            if event["source"]:
                sources[event["source"]] += 1

        if event["ticket_id"]:
            ticket_times[event["ticket_id"]].setdefault(event_type, occurred_at)
        elif event["booking_id"]:
            booking_times[event["booking_id"]].setdefault(event_type, occurred_at)

    wait_seconds = []
    service_seconds = []
    timing_subjects = list(ticket_times.values()) + list(booking_times.values())
    for times in timing_subjects:
        checked_in = times.get(QueueEvent.CHECKED_IN)
        called = times.get(QueueEvent.CALLED)
        completed = times.get(QueueEvent.COMPLETED)

        if checked_in and called and called >= checked_in:
            wait_seconds.append((called - checked_in).total_seconds())
        if called and completed and completed >= called:
            service_seconds.append((completed - called).total_seconds())

    outcome_total = summary["completed"] + summary["no_show"]
    completion_rate = (
        round(summary["completed"] / outcome_total * 100, 2) if outcome_total else None
    )
    no_show_rate = (
        round(summary["no_show"] / outcome_total * 100, 2) if outcome_total else None
    )

    return {
        "branch_id": branch.id,
        "branch_name": branch.name,
        "period": {
            "start_date": start_date,
            "end_date": end_date,
        },
        "summary": summary,
        "timing": {
            "average_actual_wait_minutes": _round_minutes(wait_seconds),
            "average_service_minutes": _round_minutes(service_seconds),
            "measured_waits": len(wait_seconds),
            "measured_services": len(service_seconds),
        },
        "outcomes": {
            "completion_rate_percent": completion_rate,
            "no_show_rate_percent": no_show_rate,
        },
        "queue_type_check_ins": dict(sorted(queue_types.items())),
        "source_check_ins": dict(sorted(sources.items())),
        "services": sorted(
            services.values(),
            key=lambda item: (item["service_name"], item["service_id"] or 0),
        ),
        "daily_activity": [
            {"date": day, **counts} for day, counts in sorted(daily.items())
        ],
    }

from __future__ import annotations

from datetime import date, datetime, time, timedelta
import os
import random

from django.db import transaction
from django.utils import timezone

from bookings.models import Booking
from queues.busy_day import (
    CUSTOMER_PREFIX,
    SCENARIO_BRANCH_CODE,
    SCENARIO_BRANCH_NAME,
    SERVICE_PROFILES,
    SERVICE_SEQUENCE,
    STAFF_SPECS,
    activate_simulation_booking,
    parse_customer_index,
    priority_positions,
    scenario_customer_prefix,
    scenario_username,
    service_code_for_index,
)
from queues.events import record_queue_event
from queues.models import QueueEvent, QueueTicket


SCENARIO_VERSION = "resilient-day-v2"
OPERATING_START = time(9, 0)
OPERATING_END = time(18, 0)
LAST_APPOINTMENT = time(17, 45)
NO_SHOW_GRACE_MINUTES = 10
DEFAULT_CUSTOMERS = 110
DEFAULT_NO_SHOWS = 10

SCENARIO_MANAGER_USERNAME = "ml_manager"
SCENARIO_RECEPTIONIST_USERNAME = "ml_receptionist"
SCENARIO_MANAGER_PASSWORD = os.getenv("SMARTQ_TRAINING_MANAGER_PASSWORD")
SCENARIO_RECEPTIONIST_PASSWORD = os.getenv("SMARTQ_TRAINING_RECEPTION_PASSWORD")


def appointment_slots(customer_count: int) -> list[time]:
    """Preserve the Day 61 15-minute arrival rhythm inside the new 09:00-18:00 day."""
    slots: list[time] = []
    cursor = datetime.combine(date.min, OPERATING_START)
    end = datetime.combine(date.min, LAST_APPOINTMENT)
    while cursor <= end:
        slots.append(cursor.time())
        cursor += timedelta(minutes=15)

    result = [slots[index % len(slots)] for index in range(customer_count)]
    return sorted(result)


def no_show_positions(
    customer_count: int,
    target_date: date,
    no_show_count: int = DEFAULT_NO_SHOWS,
) -> set[int]:
    """
    Select deterministic-random seeded absences.

    The first three customers remain eligible to arrive at opening so the Day 61
    all-counters-start checkpoint remains comparable. All later positions are
    sampled without replacement and the same date always produces the same set.
    """
    if customer_count <= 0 or no_show_count <= 0:
        return set()
    if no_show_count > max(customer_count - 3, 0):
        raise ValueError("No-show count leaves too few opening customers.")

    candidates = list(range(3, customer_count))
    rng = random.Random(f"{SCENARIO_VERSION}:{target_date.isoformat()}:no-shows")
    return set(rng.sample(candidates, no_show_count))


def is_seeded_no_show(
    username: str,
    *,
    target_date: date,
    customer_count: int = DEFAULT_CUSTOMERS,
    no_show_count: int = DEFAULT_NO_SHOWS,
) -> bool:
    if not username.startswith(scenario_customer_prefix(target_date)):
        return False
    zero_index = parse_customer_index(username) - 1
    return zero_index in no_show_positions(customer_count, target_date, no_show_count)


def planned_service_minutes_for_booking(booking: Booking, target_date: date) -> int:
    """
    Return reproducible actual duration for seeded and live extra customers.

    Seeded users retain Day 61's service-duration families. Customer/reception
    extras use the same duration options but a stable booking-based rotation so
    the live runner can complete them through the normal queue lifecycle too.
    """
    service_code = booking.service.service_code
    profile = SERVICE_PROFILES[service_code]
    options = profile["duration_minutes"]

    if booking.user_id and booking.user.username.startswith(
        scenario_customer_prefix(target_date)
    ):
        customer_index = parse_customer_index(booking.user.username)
        occurrence = (customer_index - 1) // len(SERVICE_SEQUENCE)
        rng = random.Random(
            f"{SCENARIO_VERSION}:{target_date.isoformat()}:{service_code}:seeded"
        )
        rotation = rng.randrange(len(options))
        return int(options[(occurrence + rotation) % len(options)])

    stable_identity = f"booking-{booking.pk}"
    rng = random.Random(
        f"{SCENARIO_VERSION}:{target_date.isoformat()}:{service_code}:{stable_identity}"
    )
    return int(options[rng.randrange(len(options))])


def appointment_datetime(booking: Booking):
    value = datetime.combine(booking.booking_date, booking.booking_time)
    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone.get_current_timezone())
    return value


def operating_datetime(target_date: date, value: time):
    result = datetime.combine(target_date, value)
    if timezone.is_naive(result):
        result = timezone.make_aware(result, timezone.get_current_timezone())
    return result


@transaction.atomic
def mark_scheduled_no_show(booking: Booking, *, occurred_at=None):
    """Mark one seeded absent appointment NO_SHOW without putting it in WAITING."""
    booking = Booking.objects.select_for_update().get(pk=booking.pk)
    if booking.checked_in_at is not None:
        return None, "already_checked_in"
    if booking.status in {Booking.CANCELLED, Booking.COMPLETED, Booking.NO_SHOW}:
        return getattr(booking, "queueticket", None), "final_state"

    ticket = QueueTicket.objects.select_for_update().get(booking=booking)
    old_ticket_status = ticket.status
    old_booking_status = booking.status

    booking.status = Booking.NO_SHOW
    booking.save(update_fields=["status"])
    ticket.status = QueueTicket.NO_SHOW
    ticket.assigned_counter = None
    ticket.save(update_fields=["status", "assigned_counter"])

    if occurred_at is None:
        occurred_at = timezone.now()
    record_queue_event(
        QueueEvent.NO_SHOW,
        ticket=ticket,
        booking=booking,
        source=QueueEvent.SYSTEM,
        from_ticket_status=old_ticket_status,
        to_ticket_status=QueueTicket.NO_SHOW,
        from_booking_status=old_booking_status,
        to_booking_status=Booking.NO_SHOW,
        occurred_at=occurred_at,
        metadata={
            "simulation": SCENARIO_VERSION,
            "reason": "scheduled_absence",
            "grace_minutes": NO_SHOW_GRACE_MINUTES,
        },
    )
    return ticket, None


__all__ = [
    "CUSTOMER_PREFIX",
    "SCENARIO_BRANCH_CODE",
    "SCENARIO_BRANCH_NAME",
    "SERVICE_PROFILES",
    "SERVICE_SEQUENCE",
    "STAFF_SPECS",
    "activate_simulation_booking",
    "priority_positions",
    "scenario_customer_prefix",
    "scenario_username",
    "service_code_for_index",
]

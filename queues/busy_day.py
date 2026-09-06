from __future__ import annotations

from datetime import date, datetime, time, timedelta
import os
import random
import re

from django.db import transaction
from django.utils import timezone

from bookings.models import Booking
from .events import record_queue_event
from .models import QueueEvent, QueueTicket


SCENARIO_BRANCH_CODE = "ML01"
SCENARIO_BRANCH_NAME = "Smart Q Training Branch"
SCENARIO_VERSION = "busy-day-v1"
CUSTOMER_PREFIX = "mlbusy_"

SERVICE_SEQUENCE = ("COLLECT", "IDAPP", "PASSPORT")
SERVICE_PROFILES = {
    "COLLECT": {
        "name": "Collections",
        "average_minutes": 10,
        "duration_minutes": (10, 5, 13, 8, 11, 6, 10, 15, 9),
    },
    "IDAPP": {
        "name": "ID Applications",
        "average_minutes": 15,
        "duration_minutes": (15, 8, 19, 12, 17, 10, 15, 22, 14),
    },
    "PASSPORT": {
        "name": "Passport Applications",
        "average_minutes": 20,
        "duration_minutes": (20, 12, 27, 17, 24, 15, 20, 30, 19),
    },
}

STAFF_SPECS = (
    ("ml_counter_general_1", "General", "One", QueueTicket.GENERAL, "1"),
    ("ml_counter_general_2", "General", "Two", QueueTicket.GENERAL, "2"),
    ("ml_counter_priority_1", "Priority", "One", QueueTicket.PRIORITY, "3"),
)

SCENARIO_MANAGER_USERNAME = "ml_manager"
# Optional local-only observer credential. Never commit a training password to the
# repository. If the variable is absent the observer account gets an unusable
# password and the simulator itself still runs normally.
SCENARIO_MANAGER_PASSWORD = os.getenv("SMARTQ_TRAINING_MANAGER_PASSWORD")


def scenario_customer_prefix(target_date: date) -> str:
    return f"{CUSTOMER_PREFIX}{target_date:%Y%m%d}_"


def scenario_username(target_date: date, index: int) -> str:
    return f"{scenario_customer_prefix(target_date)}{index:03d}"


def parse_customer_index(username: str) -> int:
    match = re.search(r"_(\d{3})$", username or "")
    if not match:
        raise ValueError(f"{username!r} is not a Smart Q busy-day customer username")
    return int(match.group(1))


def appointment_slots(customer_count: int) -> list[time]:
    """Spread appointments from 08:00 to 15:45 in 15-minute slots."""
    slots: list[time] = []
    cursor = datetime.combine(date.min, time(8, 0))
    end = datetime.combine(date.min, time(15, 45))
    while cursor <= end:
        slots.append(cursor.time())
        cursor += timedelta(minutes=15)

    result = [slots[index % len(slots)] for index in range(customer_count)]
    return sorted(result)


def priority_positions(customer_count: int) -> set[int]:
    """Return exactly about 10 percent priority positions with one at 08:00."""
    if customer_count <= 0:
        return set()
    priority_count = max(1, round(customer_count * 0.10))
    positions = {0}
    if priority_count == 1:
        return positions

    step = max(customer_count // priority_count, 1)
    cursor = step
    while len(positions) < priority_count and cursor < customer_count:
        positions.add(cursor)
        cursor += step

    cursor = customer_count - 1
    while len(positions) < priority_count and cursor >= 0:
        positions.add(cursor)
        cursor -= 1
    return positions


def service_code_for_index(index: int) -> str:
    return SERVICE_SEQUENCE[(index - 1) % len(SERVICE_SEQUENCE)]


def planned_service_minutes(username: str, service_code: str, target_date: date) -> int:
    """Return varied but reproducible service time for one synthetic visit."""
    profile = SERVICE_PROFILES[service_code]
    options = profile["duration_minutes"]
    customer_index = parse_customer_index(username)
    occurrence = (customer_index - 1) // len(SERVICE_SEQUENCE)
    rng = random.Random(f"{SCENARIO_VERSION}:{target_date.isoformat()}:{service_code}")
    rotation = rng.randrange(len(options))
    return int(options[(occurrence + rotation) % len(options)])


def appointment_datetime(booking: Booking):
    value = datetime.combine(booking.booking_date, booking.booking_time)
    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone.get_current_timezone())
    return value


@transaction.atomic
def activate_simulation_booking(booking: Booking, *, occurred_at=None):
    """Activate a scheduled synthetic booking through the normal queue event path."""
    booking = Booking.objects.select_for_update().select_related(
        "branch", "service", "user", "user__profile"
    ).get(pk=booking.pk)

    if booking.checked_in_at is not None:
        return booking.queueticket, "already_checked_in"
    if booking.status in {Booking.CANCELLED, Booking.COMPLETED, Booking.NO_SHOW}:
        return None, "final_state"

    ticket = QueueTicket.objects.select_for_update().get(booking=booking)
    if ticket.status in {QueueTicket.CANCELLED, QueueTicket.COMPLETED, QueueTicket.NO_SHOW}:
        return None, "final_state"

    if occurred_at is None:
        occurred_at = timezone.now()

    old_ticket_status = ticket.status
    old_booking_status = booking.status
    ticket.status = QueueTicket.WAITING
    ticket.assigned_counter = None
    ticket.save(update_fields=["status", "assigned_counter"])

    booking.checked_in_at = occurred_at
    booking.status = Booking.PENDING
    booking.save(update_fields=["checked_in_at", "status"])

    record_queue_event(
        QueueEvent.CHECKED_IN,
        ticket=ticket,
        booking=booking,
        source=QueueEvent.SYSTEM,
        from_ticket_status=old_ticket_status,
        to_ticket_status=QueueTicket.WAITING,
        from_booking_status=old_booking_status,
        to_booking_status=Booking.PENDING,
        occurred_at=occurred_at,
        metadata={"simulation": SCENARIO_VERSION},
    )
    return ticket, None

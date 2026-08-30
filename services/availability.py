from datetime import datetime, timedelta

from django.utils import timezone

from bookings.models import Booking
from .models import BranchService


RESERVED_BOOKING_STATUSES = [
    Booking.PENDING,
    Booking.CONFIRMED,
    Booking.COMPLETED,
    Booking.NO_SHOW,
]


def get_branch_service(branch, service, *, lock=False):
    """Return an active BranchService mapping for an active branch/service pair."""
    queryset = BranchService.objects.select_related("branch", "service")
    if lock:
        queryset = queryset.select_for_update()

    return queryset.filter(
        branch=branch,
        service=service,
        branch__is_active=True,
        service__is_active=True,
        is_active=True,
    ).first()


def _aware_local_datetime(day, clock_time):
    """Combine a local date/time and make it timezone-aware for comparisons."""
    value = datetime.combine(day, clock_time)
    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone.get_current_timezone())
    return value


def generate_slot_times(branch, service, booking_date):
    """
    Generate valid appointment start times for one branch/service/date.

    The approved Day 32 product rule is that slot duration equals
    Service.average_service_time. A slot is emitted only when the whole service
    duration fits inside branch operating hours.
    """
    duration_minutes = service.average_service_time
    if not duration_minutes or duration_minutes <= 0:
        return []

    opening = _aware_local_datetime(booking_date, branch.opening_time)
    closing = _aware_local_datetime(booking_date, branch.closing_time)
    duration = timedelta(minutes=duration_minutes)

    slots = []
    current = opening
    while current + duration <= closing:
        slots.append(current.time().replace(tzinfo=None))
        current += duration

    return slots


def get_reserved_booking_count(branch, service, booking_date, booking_time, exclude_booking=None):
    """Count online appointments that currently reserve capacity in one slot."""
    queryset = Booking.objects.filter(
        branch=branch,
        service=service,
        booking_date=booking_date,
        booking_time=booking_time,
        source=Booking.ONLINE,
        status__in=RESERVED_BOOKING_STATUSES,
    )

    if exclude_booking is not None:
        queryset = queryset.exclude(pk=exclude_booking.pk)

    return queryset.count()


def get_slot_availability(branch, service, booking_date, *, now=None, exclude_booking=None):
    """Return backend-generated slots and remaining capacity for a date."""
    mapping = get_branch_service(branch, service)
    if mapping is None:
        return []

    if booking_date < timezone.localdate():
        return []

    if now is None:
        now = timezone.now()

    results = []
    for slot_time in generate_slot_times(branch, service, booking_date):
        slot_datetime = _aware_local_datetime(booking_date, slot_time)

        # Today's appointment choices must still be in the future.
        if slot_datetime <= now:
            continue

        booked = get_reserved_booking_count(
            branch,
            service,
            booking_date,
            slot_time,
            exclude_booking=exclude_booking,
        )
        remaining = max(mapping.max_bookings_per_slot - booked, 0)

        results.append(
            {
                "time": slot_time,
                "capacity": mapping.max_bookings_per_slot,
                "booked": booked,
                "remaining": remaining,
                "is_available": remaining > 0,
            }
        )

    return results


def validate_booking_slot(branch, service, booking_date, booking_time, *, exclude_booking=None):
    """
    Validate branch-service support, slot alignment and remaining capacity.

    Returns (mapping, error_code). Callers that create/update a Booking inside a
    transaction should re-run this with the mapping row locked to avoid two
    concurrent requests both consuming the final slot.
    """
    mapping = get_branch_service(branch, service)
    if mapping is None:
        return None, "service_not_offered"

    if booking_date < timezone.localdate():
        return mapping, "past_date"

    valid_slots = generate_slot_times(branch, service, booking_date)
    if booking_time not in valid_slots:
        return mapping, "invalid_slot"

    slot_datetime = _aware_local_datetime(booking_date, booking_time)
    if slot_datetime <= timezone.now():
        return mapping, "past_slot"

    booked = get_reserved_booking_count(
        branch,
        service,
        booking_date,
        booking_time,
        exclude_booking=exclude_booking,
    )
    if booked >= mapping.max_bookings_per_slot:
        return mapping, "slot_full"

    return mapping, None

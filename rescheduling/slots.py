from datetime import timedelta

from services.availability import get_slot_availability as get_branch_slot_availability


DEFAULT_MAX_SLOTS = 5
DEFAULT_DAYS_AHEAD = 14


def get_available_reschedule_slots(
    booking,
    start_date=None,
    days_ahead=DEFAULT_DAYS_AHEAD,
    max_slots=DEFAULT_MAX_SLOTS,
):
    """
    Return future capacity-safe appointment choices for a disrupted booking.

    Day 35 deliberately delegates slot generation and capacity rules to the
    Day 32 BranchService availability engine. Rescheduling must not maintain a
    second definition of branch hours, slot duration, or slot capacity.
    """
    if booking is None or max_slots <= 0 or days_ahead <= 0:
        return []

    if start_date is None:
        start_date = booking.booking_date + timedelta(days=1)

    choices = []
    for day_offset in range(days_ahead):
        target_date = start_date + timedelta(days=day_offset)
        slots = get_branch_slot_availability(
            booking.branch,
            booking.service,
            target_date,
            exclude_booking=booking,
        )

        for slot in slots:
            if not slot["is_available"]:
                continue

            choices.append(
                {
                    "date": target_date,
                    "time": slot["time"],
                    "capacity": slot["capacity"],
                    "booked_count": slot["booked"],
                    "available_count": slot["remaining"],
                    "is_recommended": len(choices) == 0,
                }
            )

            if len(choices) >= max_slots:
                return choices

    return choices

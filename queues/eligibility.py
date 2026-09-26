from datetime import datetime

from django.utils import timezone

from bookings.models import Booking


def get_booking_datetime(booking):
    appointment_at = datetime.combine(booking.booking_date, booking.booking_time)
    if timezone.is_naive(appointment_at):
        appointment_at = timezone.make_aware(
            appointment_at,
            timezone.get_current_timezone(),
        )
    return appointment_at


def get_service_eligible_at(booking):
    """
    Return the earliest instant at which this booking may be called.

    Walk-ins become eligible when they check in. Appointments may check in early,
    but they do not become service-eligible before their booked appointment time.
    """
    checked_in_at = booking.checked_in_at
    if checked_in_at is None:
        return None

    if booking.source == Booking.WALK_IN:
        return checked_in_at

    appointment_at = get_booking_datetime(booking)
    return max(checked_in_at, appointment_at)


def is_service_eligible(booking, *, now=None):
    if now is None:
        now = timezone.now()
    eligible_at = get_service_eligible_at(booking)
    return eligible_at is not None and eligible_at <= now


def service_eligibility_delay_seconds(booking, *, now=None):
    if now is None:
        now = timezone.now()
    eligible_at = get_service_eligible_at(booking)
    if eligible_at is None:
        return 0
    return max(int(round((eligible_at - now).total_seconds())), 0)

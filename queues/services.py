from datetime import datetime, timedelta

from django.db import transaction
from django.db.models import Case, IntegerField, Value, When
from django.utils import timezone

from accounts.models import Profile
from bookings.models import Booking
from counters.models import Counter
from .models import QueueTicket


CHECK_IN_OPEN_HOURS = 6


def calculate_age(date_of_birth):
    """Calculate age using Smart Q's current local date."""
    today = timezone.localdate()
    age = today.year - date_of_birth.year

    if (today.month, today.day) < (date_of_birth.month, date_of_birth.day):
        age -= 1

    return age


def get_priority_attributes(booking):
    """Return age/gender/disability attributes for registered or guest customers."""
    if booking.user_id:
        profile = booking.user.profile
        return {
            "date_of_birth": profile.date_of_birth,
            "gender": profile.gender,
            "disability_status": profile.disability_status,
        }

    guest = booking.guest_customer
    return {
        "date_of_birth": guest.date_of_birth,
        "gender": guest.gender,
        "disability_status": guest.disability_status,
    }


def determine_queue_type(booking):
    """Apply the same priority policy to account holders and guest walk-ins."""
    attributes = get_priority_attributes(booking)
    age = calculate_age(attributes["date_of_birth"])

    if age >= 55:
        return QueueTicket.PRIORITY

    if attributes["disability_status"]:
        return QueueTicket.PRIORITY

    if attributes["gender"] == Profile.FEMALE and booking.is_pregnant:
        return QueueTicket.PRIORITY

    return QueueTicket.GENERAL


def get_booking_datetime(booking):
    """Return the booking's aware appointment datetime."""
    booking_datetime = datetime.combine(booking.booking_date, booking.booking_time)
    if timezone.is_naive(booking_datetime):
        booking_datetime = timezone.make_aware(
            booking_datetime,
            timezone.get_current_timezone(),
        )
    return booking_datetime


def get_check_in_opens_at(booking):
    """Check-in opens six hours before the appointment datetime."""
    return get_booking_datetime(booking) - timedelta(hours=CHECK_IN_OPEN_HOURS)


def generate_queue_number(booking, queue_type):
    prefix = "A" if queue_type == QueueTicket.GENERAL else "P"

    latest_ticket = QueueTicket.objects.filter(
        booking__branch=booking.branch,
        booking__booking_date=booking.booking_date,
        queue_type=queue_type,
    ).order_by("-id").first()

    if latest_ticket:
        last_number = int(latest_ticket.queue_number[1:])
        new_number = last_number + 1
    else:
        new_number = 1

    return f"{prefix}{new_number:03d}"


def create_queue_ticket_for_booking(booking):
    """Create a non-live SCHEDULED ticket for a future/online appointment."""
    queue_type = determine_queue_type(booking)
    queue_number = generate_queue_number(booking, queue_type)

    return QueueTicket.objects.create(
        booking=booking,
        queue_type=queue_type,
        queue_number=queue_number,
        status=QueueTicket.SCHEDULED,
    )


@transaction.atomic
def cancel_expired_unchecked_booking(booking, now=None):
    """
    Cancel an appointment whose appointment time passed without check-in.

    Product rule: a customer who never checked in was never in the live queue,
    so this outcome is CANCELLED rather than NO_SHOW.
    """
    if now is None:
        now = timezone.now()

    booking = Booking.objects.select_for_update().get(pk=booking.pk)

    if booking.checked_in_at is not None:
        return False
    if booking.status in [Booking.CANCELLED, Booking.COMPLETED, Booking.NO_SHOW]:
        return False
    if now <= get_booking_datetime(booking):
        return False

    booking.status = Booking.CANCELLED
    booking.save(update_fields=["status"])

    try:
        ticket = QueueTicket.objects.select_for_update().get(booking=booking)
    except QueueTicket.DoesNotExist:
        ticket = None

    if ticket:
        ticket.status = QueueTicket.CANCELLED
        ticket.assigned_counter = None
        ticket.save(update_fields=["status", "assigned_counter"])

    return True


@transaction.atomic
def check_in_booking(booking):
    """Activate an eligible online or in-person booking into the live queue."""
    booking = Booking.objects.select_for_update().select_related(
        "branch", "service", "user", "user__profile", "guest_customer"
    ).get(pk=booking.pk)

    if booking.status in [Booking.CANCELLED, Booking.COMPLETED, Booking.NO_SHOW]:
        return None, "final_state"

    if booking.checked_in_at is not None:
        try:
            return booking.queueticket, "already_checked_in"
        except QueueTicket.DoesNotExist:
            return None, "already_checked_in"

    now = timezone.now()
    appointment_at = get_booking_datetime(booking)

    if now > appointment_at:
        cancel_expired_unchecked_booking(booking, now=now)
        return None, "expired_cancelled"

    if now < get_check_in_opens_at(booking):
        return None, "too_early"

    try:
        ticket = QueueTicket.objects.select_for_update().get(booking=booking)
    except QueueTicket.DoesNotExist:
        ticket = create_queue_ticket_for_booking(booking)

    if ticket.status in [
        QueueTicket.CANCELLED,
        QueueTicket.COMPLETED,
        QueueTicket.NO_SHOW,
    ]:
        return None, "final_state"

    new_queue_type = determine_queue_type(booking)
    if new_queue_type != ticket.queue_type:
        ticket.queue_type = new_queue_type
        ticket.queue_number = generate_queue_number(booking, new_queue_type)

    ticket.status = QueueTicket.WAITING
    ticket.assigned_counter = None
    ticket.save(
        update_fields=[
            "queue_type",
            "queue_number",
            "status",
            "assigned_counter",
        ]
    )

    booking.checked_in_at = now
    booking.status = Booking.PENDING
    booking.save(update_fields=["checked_in_at", "status"])

    return ticket, None


def get_current_ticket(counter):
    return QueueTicket.objects.filter(
        assigned_counter=counter,
        status=QueueTicket.SERVING,
    ).select_related("booking", "booking__branch", "booking__service").first()


def get_waiting_tickets(branch, booking_date=None, queue_type=None):
    """Return customers activated into the live queue for a branch/date."""
    if booking_date is None:
        booking_date = timezone.localdate()

    tickets = QueueTicket.objects.filter(
        booking__branch=branch,
        booking__booking_date=booking_date,
        booking__checked_in_at__isnull=False,
        status=QueueTicket.WAITING,
        assigned_counter__isnull=True,
        booking__status__in=[Booking.PENDING, Booking.CONFIRMED],
    ).select_related(
        "booking",
        "booking__branch",
        "booking__service",
        "booking__user",
        "booking__guest_customer",
    )

    if queue_type:
        tickets = tickets.filter(queue_type=queue_type)
        return tickets.order_by("booking__checked_in_at", "id")

    queue_type_rank = Case(
        When(queue_type=QueueTicket.PRIORITY, then=Value(0)),
        When(queue_type=QueueTicket.GENERAL, then=Value(1)),
        default=Value(2),
        output_field=IntegerField(),
    )

    return tickets.annotate(
        queue_type_rank=queue_type_rank
    ).order_by("queue_type_rank", "booking__checked_in_at", "id")


@transaction.atomic
def call_next_ticket(counter, booking_date=None):
    """Assign the next checked-in waiting customer to an OPEN counter."""
    if counter.status != Counter.OPEN:
        return None

    if booking_date is None:
        booking_date = timezone.localdate()

    current_ticket = QueueTicket.objects.select_for_update().filter(
        assigned_counter=counter,
        status=QueueTicket.SERVING,
    ).first()
    if current_ticket:
        return None

    ticket = QueueTicket.objects.select_for_update().filter(
        queue_type=counter.queue_type,
        booking__branch=counter.branch,
        booking__booking_date=booking_date,
        booking__checked_in_at__isnull=False,
        booking__status__in=[Booking.PENDING, Booking.CONFIRMED],
        status=QueueTicket.WAITING,
        assigned_counter__isnull=True,
    ).order_by("booking__checked_in_at", "id").first()

    if ticket is None:
        return None

    ticket.assigned_counter = counter
    ticket.status = QueueTicket.SERVING
    ticket.save(update_fields=["assigned_counter", "status"])

    if ticket.booking.status == Booking.PENDING:
        ticket.booking.status = Booking.CONFIRMED
        ticket.booking.save(update_fields=["status"])

    return ticket


@transaction.atomic
def complete_current_ticket(counter):
    ticket = QueueTicket.objects.select_for_update().filter(
        assigned_counter=counter,
        status=QueueTicket.SERVING,
    ).select_related("booking").first()

    if ticket is None:
        return None

    ticket.status = QueueTicket.COMPLETED
    ticket.assigned_counter = None
    ticket.save(update_fields=["status", "assigned_counter"])

    ticket.booking.status = Booking.COMPLETED
    ticket.booking.save(update_fields=["status"])

    return ticket


@transaction.atomic
def mark_current_ticket_no_show(counter):
    """
    Mark a called/serving customer as NO_SHOW.

    This only applies after check-in. Unchecked expired appointments are
    cancelled instead and never enter the live queue.
    """
    ticket = QueueTicket.objects.select_for_update().filter(
        assigned_counter=counter,
        status=QueueTicket.SERVING,
        booking__checked_in_at__isnull=False,
    ).select_related("booking").first()

    if ticket is None:
        return None

    ticket.status = QueueTicket.NO_SHOW
    ticket.assigned_counter = None
    ticket.save(update_fields=["status", "assigned_counter"])

    ticket.booking.status = Booking.NO_SHOW
    ticket.booking.save(update_fields=["status"])

    return ticket

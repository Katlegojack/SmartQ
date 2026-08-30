from datetime import datetime, timedelta

from django.db import transaction
from django.db.models import Case, IntegerField, Value, When
from django.utils import timezone

from accounts.models import Profile
from bookings.models import Booking
from counters.models import Counter
from .models import QueueTicket


# Product rule: customers may activate their live queue ticket online starting
# six hours before the booked appointment time. Reception can use the same
# activation rule for an in-person check-in.
CHECK_IN_OPEN_HOURS = 6


# Business logic: calculate a user's age from their date of birth.
def calculate_age(date_of_birth):
    today = timezone.localdate()
    age = today.year - date_of_birth.year

    if (today.month, today.day) < (date_of_birth.month, date_of_birth.day):
        age -= 1

    return age


# Business logic: decide whether a booking belongs to General or Priority.
def determine_queue_type(booking):
    profile = booking.user.profile
    age = calculate_age(profile.date_of_birth)

    if age >= 55:
        return QueueTicket.PRIORITY

    if profile.disability_status:
        return QueueTicket.PRIORITY

    if profile.gender == Profile.FEMALE and booking.is_pregnant:
        return QueueTicket.PRIORITY

    return QueueTicket.GENERAL


def get_booking_datetime(booking):
    """Return the booking's date/time as an aware datetime in Smart Q's timezone."""
    booking_datetime = datetime.combine(booking.booking_date, booking.booking_time)
    if timezone.is_naive(booking_datetime):
        booking_datetime = timezone.make_aware(
            booking_datetime,
            timezone.get_current_timezone(),
        )
    return booking_datetime


def get_check_in_opens_at(booking):
    """Return the exact datetime when online/in-person check-in becomes available."""
    return get_booking_datetime(booking) - timedelta(hours=CHECK_IN_OPEN_HOURS)


# Business logic: generate the next customer-friendly queue number.
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


# A booking gets a digital ticket immediately, but it does not join the live
# waiting queue until online or in-person check-in activates that ticket.
def create_queue_ticket_for_booking(booking):
    queue_type = determine_queue_type(booking)
    queue_number = generate_queue_number(booking, queue_type)

    return QueueTicket.objects.create(
        booking=booking,
        queue_type=queue_type,
        queue_number=queue_number,
        status=QueueTicket.SCHEDULED,
    )


@transaction.atomic
def check_in_booking(booking):
    """
    Activate an eligible scheduled booking into the live queue.

    Check-in may happen online or in person. It opens six hours before the
    booked appointment time. The booking must still belong to the current
    service date so a stale appointment cannot enter a later day's live queue.

    Returns (ticket, error_code). error_code is None on success.
    """
    booking = Booking.objects.select_for_update().select_related(
        "branch", "service", "user", "user__profile"
    ).get(pk=booking.pk)

    if booking.status in [Booking.CANCELLED, Booking.COMPLETED, Booking.NO_SHOW]:
        return None, "final_state"

    if booking.checked_in_at is not None:
        try:
            return booking.queueticket, "already_checked_in"
        except QueueTicket.DoesNotExist:
            return None, "already_checked_in"

    now = timezone.now()
    if now < get_check_in_opens_at(booking):
        return None, "too_early"

    # Smart Q's current live-queue engine is date-scoped. Once the booking day
    # has passed, the appointment must be handled by the later late/no-show or
    # rescheduling policy rather than entering a new day's queue silently.
    if booking.booking_date != timezone.localdate():
        return None, "wrong_date"

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

    # Recalculate priority at queue activation because profile information may
    # have changed since booking creation. If the queue class changes,
    # regenerate the visible queue number so A/P prefix and queue type agree.
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

    # checked_in_at means live-queue activation time. It does not prove that
    # the customer is physically inside the branch.
    booking.checked_in_at = now
    booking.status = Booking.PENDING
    booking.save(update_fields=["checked_in_at", "status"])

    return ticket, None


def get_current_ticket(counter):
    """Return the ticket currently being served at a counter, if one exists."""
    return QueueTicket.objects.filter(
        assigned_counter=counter,
        status=QueueTicket.SERVING,
    ).select_related("booking", "booking__branch", "booking__service").first()


def get_waiting_tickets(branch, booking_date=None, queue_type=None):
    """Return customers whose tickets have been activated into the live queue."""
    if booking_date is None:
        booking_date = timezone.localdate()

    tickets = QueueTicket.objects.filter(
        booking__branch=branch,
        booking__booking_date=booking_date,
        booking__checked_in_at__isnull=False,
        status=QueueTicket.WAITING,
        assigned_counter__isnull=True,
        booking__status__in=[Booking.PENDING, Booking.CONFIRMED],
    ).select_related("booking", "booking__branch", "booking__service")

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
    """Assign the next activated waiting customer to an OPEN counter."""
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
    """Complete the customer currently being served and release the counter."""
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
    """Mark the currently served customer as a no-show and release the counter."""
    ticket = QueueTicket.objects.select_for_update().filter(
        assigned_counter=counter,
        status=QueueTicket.SERVING,
    ).select_related("booking").first()

    if ticket is None:
        return None

    ticket.status = QueueTicket.NO_SHOW
    ticket.assigned_counter = None
    ticket.save(update_fields=["status", "assigned_counter"])

    ticket.booking.status = Booking.NO_SHOW
    ticket.booking.save(update_fields=["status"])

    return ticket

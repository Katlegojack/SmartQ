from django.db import transaction
from django.db.models import Case, IntegerField, Value, When
from django.utils import timezone

from accounts.models import Profile
from bookings.models import Booking
from counters.models import Counter
from .models import QueueTicket


# Business logic: calculate a user's age from their date of birth.
def calculate_age(date_of_birth):
    today = timezone.now().date()
    age = today.year - date_of_birth.year

    # If the user's birthday has not happened yet this year, subtract one year.
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

    # Pregnancy priority only applies when the profile is female and the booking
    # explicitly indicates pregnancy.
    if profile.gender == Profile.FEMALE and booking.is_pregnant:
        return QueueTicket.PRIORITY

    return QueueTicket.GENERAL


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


# Business logic: create a QueueTicket automatically from a Booking.
def create_queue_ticket_for_booking(booking):
    queue_type = determine_queue_type(booking)
    queue_number = generate_queue_number(booking, queue_type)

    return QueueTicket.objects.create(
        booking=booking,
        queue_type=queue_type,
        queue_number=queue_number,
        status=QueueTicket.WAITING,
    )


def get_current_ticket(counter):
    """Return the ticket currently being served at a counter, if one exists."""
    return QueueTicket.objects.filter(
        assigned_counter=counter,
        status=QueueTicket.SERVING,
    ).select_related("booking", "booking__branch", "booking__service").first()


def get_waiting_tickets(branch, booking_date=None, queue_type=None):
    """
    Return the live waiting queue for a branch.

    The optional queue_type filter allows staff displays to request only the
    General or Priority queue. By default the function uses today's date so a
    future booking is never accidentally called early.
    """
    if booking_date is None:
        booking_date = timezone.localdate()

    tickets = QueueTicket.objects.filter(
        booking__branch=branch,
        booking__booking_date=booking_date,
        status=QueueTicket.WAITING,
        assigned_counter__isnull=True,
        booking__status__in=[Booking.PENDING, Booking.CONFIRMED],
    ).select_related("booking", "booking__branch", "booking__service")

    if queue_type:
        tickets = tickets.filter(queue_type=queue_type)
        return tickets.order_by("created_at", "id")

    # For the combined waiting-room view, Priority must appear before General.
    # An explicit sort rank is used instead of relying on alphabetical strings,
    # because alphabetical ordering would incorrectly place "general" first.
    queue_type_rank = Case(
        When(queue_type=QueueTicket.PRIORITY, then=Value(0)),
        When(queue_type=QueueTicket.GENERAL, then=Value(1)),
        default=Value(2),
        output_field=IntegerField(),
    )

    return tickets.annotate(
        queue_type_rank=queue_type_rank
    ).order_by("queue_type_rank", "created_at", "id")


@transaction.atomic
def call_next_ticket(counter, booking_date=None):
    """
    Assign the next waiting customer to an OPEN counter.

    The database transaction prevents queue-state changes from being split
    across multiple operations. select_for_update() also prepares this flow for
    production databases such as PostgreSQL where multiple staff members may
    press "Call Next" at nearly the same time.
    """
    if counter.status != Counter.OPEN:
        return None

    if booking_date is None:
        booking_date = timezone.localdate()

    # Do not allow a counter to serve two customers at once.
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
        booking__status__in=[Booking.PENDING, Booking.CONFIRMED],
        status=QueueTicket.WAITING,
        assigned_counter__isnull=True,
    ).order_by("created_at", "id").first()

    if ticket is None:
        return None

    ticket.assigned_counter = counter
    ticket.status = QueueTicket.SERVING
    ticket.save(update_fields=["assigned_counter", "status"])

    # Keep the booking lifecycle aligned with the queue lifecycle.
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

    # A completed queue interaction must also appear completed in booking history.
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

    # Keep booking history and queue history consistent.
    ticket.booking.status = Booking.NO_SHOW
    ticket.booking.save(update_fields=["status"])

    return ticket

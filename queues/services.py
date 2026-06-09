from django.utils import timezone

from accounts.models import Profile
from .models import QueueTicket


# Business logic: calculate user's age from date of birth
def calculate_age(date_of_birth):
    today = timezone.now().date()

    age = today.year - date_of_birth.year

    # CHANGED: fixed birthday comparison.
    # We compare month/day, not year/day.
    if (today.month, today.day) < (date_of_birth.month, date_of_birth.day):
        age -= 1

    return age


# Business logic: decide whether booking should be General or Priority
def determine_queue_type(booking):
    profile = booking.user.profile

    age = calculate_age(profile.date_of_birth)

    if age >= 55:
        return QueueTicket.PRIORITY

    if profile.disability_status:
        return QueueTicket.PRIORITY

    # CHANGED: pregnancy status is stored on Booking, not Profile.
    # Also compare gender using Profile.FEMALE.
    if profile.gender == Profile.FEMALE and booking.is_pregnant:
        return QueueTicket.PRIORITY

    return QueueTicket.GENERAL


# Business logic: generate next queue number like A001, A002, P001
def generate_queue_number(booking, queue_type):
    prefix = "A" if queue_type == QueueTicket.GENERAL else "P"

    latest_ticket = QueueTicket.objects.filter(
        # CHANGED: fixed double underscore relationship lookup.
        # QueueTicket -> Booking -> Branch
        booking__branch=booking.branch,

        # CHANGED: fixed double underscore relationship lookup.
        # QueueTicket -> Booking -> Booking Date
        booking__booking_date=booking.booking_date,

        queue_type=queue_type
    ).order_by("-id").first()

    if latest_ticket:
        last_number = int(latest_ticket.queue_number[1:])
        new_number = last_number + 1
    else:
        # CHANGED: new_number must be set to 1 for the first ticket.
        new_number = 1

    # CHANGED: return must be outside the if/else so it always returns.
    return f"{prefix}{new_number:03d}"


# Business logic: create QueueTicket automatically from Booking
def create_queue_ticket_for_booking(booking):
    # CHANGED: queue type is no longer passed manually.
    # The system decides General/Priority using business rules.
    queue_type = determine_queue_type(booking)

    queue_number = generate_queue_number(booking, queue_type)

    queue_ticket = QueueTicket.objects.create(
        booking=booking,
        queue_type=queue_type,
        queue_number=queue_number,
        status=QueueTicket.WAITING
    )

    return queue_ticket
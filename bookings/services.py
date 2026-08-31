from django.db import transaction
from django.utils import timezone

from queues.events import record_queue_event
from queues.models import QueueEvent, QueueTicket
from queues.services import create_queue_ticket_for_booking
from .models import Booking, GuestCustomer


@transaction.atomic
def create_guest_walk_in(
    *,
    branch,
    service,
    full_name,
    phone_number,
    date_of_birth,
    gender,
    disability_status=False,
    is_pregnant=False,
    actor=None,
):
    """Create a no-account guest walk-in and immediately activate the live ticket."""
    guest = GuestCustomer.objects.create(
        full_name=full_name,
        phone_number=phone_number,
        date_of_birth=date_of_birth,
        gender=gender,
        disability_status=disability_status,
    )

    now = timezone.now()
    local_now = timezone.localtime(now)
    booking = Booking.objects.create(
        user=None,
        guest_customer=guest,
        branch=branch,
        service=service,
        booking_date=local_now.date(),
        booking_time=local_now.time().replace(microsecond=0),
        is_pregnant=is_pregnant,
        status=Booking.PENDING,
        source=Booking.WALK_IN,
        checked_in_at=now,
    )

    # Walk-ins do not pass through a meaningful future SCHEDULED lifecycle, so
    # suppress that event and record their actual immediate live-queue activation.
    ticket = create_queue_ticket_for_booking(
        booking,
        actor=actor,
        record_event=False,
    )
    ticket.status = QueueTicket.WAITING
    ticket.save(update_fields=["status"])

    record_queue_event(
        QueueEvent.CHECKED_IN,
        ticket=ticket,
        booking=booking,
        actor=actor,
        from_ticket_status=QueueTicket.SCHEDULED,
        to_ticket_status=QueueTicket.WAITING,
        to_booking_status=Booking.PENDING,
        occurred_at=now,
        metadata={"check_in_mode": "walk_in_reception"},
    )
    return booking

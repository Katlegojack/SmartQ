from django.db import transaction
from django.utils import timezone

from queues.models import QueueTicket
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
):
    """
    Create a no-account guest walk-in and immediately activate the live ticket.

    Walk-ins are already at reception, so unlike an advance online appointment
    they do not pass through SCHEDULED. They enter WAITING immediately.
    """
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

    ticket = create_queue_ticket_for_booking(booking)
    ticket.status = QueueTicket.WAITING
    ticket.save(update_fields=["status"])

    return booking

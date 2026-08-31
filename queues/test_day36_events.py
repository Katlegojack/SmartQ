from datetime import date, time, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from accounts.models import Profile
from bookings.models import Booking
from branches.models import Branch
from counters.models import Counter
from counters.services import (
    assign_counter_staff,
    close_counter,
    open_counter,
    pause_counter,
    resume_counter,
)
from services.models import Service

from .analytics import get_ticket_actual_wait_minutes
from .events import get_counter_event_timeline, get_ticket_event_timeline
from .models import QueueEvent, QueueTicket
from .services import (
    call_next_ticket,
    check_in_booking,
    complete_current_ticket,
    create_queue_ticket_for_booking,
)


class Day36QueueEventTests(TestCase):
    """Regression tests for Smart Q's append-only operational history."""

    def setUp(self):
        self.branch = Branch.objects.create(
            branch_code="PTA01",
            name="Pretoria Branch",
            address="1 Main Street",
            city="Pretoria",
            opening_time=time(8, 0),
            closing_time=time(17, 0),
            is_active=True,
        )
        self.service = Service.objects.create(
            service_code="ID01",
            name="ID Application",
            description="ID service",
            average_service_time=10,
            is_active=True,
        )

        self.customer = User.objects.create_user(username="customer", password="pw")
        Profile.objects.create(
            user=self.customer,
            date_of_birth=date(1995, 1, 1),
            gender=Profile.OTHER,
            role=Profile.CUSTOMER,
        )
        self.staff = User.objects.create_user(username="staff", password="pw")
        Profile.objects.create(
            user=self.staff,
            date_of_birth=date(1990, 1, 1),
            gender=Profile.OTHER,
            role=Profile.COUNTER_STAFF,
            branch=self.branch,
        )
        self.manager = User.objects.create_user(username="manager", password="pw")
        Profile.objects.create(
            user=self.manager,
            date_of_birth=date(1985, 1, 1),
            gender=Profile.OTHER,
            role=Profile.BRANCH_MANAGER,
            branch=self.branch,
        )

        local_now = timezone.localtime(timezone.now())
        appointment = local_now + timedelta(hours=1)
        self.booking = Booking.objects.create(
            user=self.customer,
            branch=self.branch,
            service=self.service,
            booking_date=appointment.date(),
            booking_time=appointment.time().replace(microsecond=0),
            status=Booking.CONFIRMED,
            source=Booking.ONLINE,
        )
        self.counter = Counter.objects.create(
            branch=self.branch,
            counter_number=1,
            queue_type=QueueTicket.GENERAL,
            status=Counter.CLOSED,
        )

    def test_scheduled_and_check_in_events_preserve_customer_actor_snapshot(self):
        ticket = create_queue_ticket_for_booking(self.booking, actor=self.customer)
        scheduled = QueueEvent.objects.get(
            ticket=ticket,
            event_type=QueueEvent.TICKET_SCHEDULED,
        )
        self.assertEqual(scheduled.source, QueueEvent.CUSTOMER)
        self.assertEqual(scheduled.actor_username, "customer")
        self.assertEqual(scheduled.actor_role, Profile.CUSTOMER)
        self.assertEqual(scheduled.to_ticket_status, QueueTicket.SCHEDULED)

        checked_ticket, error = check_in_booking(self.booking, actor=self.customer)
        self.assertIsNone(error)
        self.assertEqual(checked_ticket.id, ticket.id)

        checked = QueueEvent.objects.get(
            ticket=ticket,
            event_type=QueueEvent.CHECKED_IN,
        )
        self.assertEqual(checked.from_ticket_status, QueueTicket.SCHEDULED)
        self.assertEqual(checked.to_ticket_status, QueueTicket.WAITING)
        self.assertEqual(checked.source, QueueEvent.CUSTOMER)

    def test_called_event_records_staff_counter_and_actual_wait(self):
        ticket = create_queue_ticket_for_booking(self.booking, actor=self.customer)
        ticket, error = check_in_booking(self.booking, actor=self.customer)
        self.assertIsNone(error)

        checked_event = QueueEvent.objects.get(
            ticket=ticket,
            event_type=QueueEvent.CHECKED_IN,
        )
        QueueEvent.objects.filter(pk=checked_event.pk).update(
            occurred_at=timezone.now() - timedelta(minutes=12)
        )

        counter, error = assign_counter_staff(
            self.counter,
            self.staff,
            actor=self.manager,
        )
        self.assertIsNone(error)
        counter, error = open_counter(counter, actor=self.staff)
        self.assertIsNone(error)

        called = call_next_ticket(counter, actor=self.staff)
        self.assertEqual(called.id, ticket.id)

        event = QueueEvent.objects.get(
            ticket=ticket,
            event_type=QueueEvent.CALLED,
        )
        self.assertEqual(event.counter_id, counter.id)
        self.assertEqual(event.actor_username, "staff")
        self.assertEqual(event.actor_role, Profile.COUNTER_STAFF)
        self.assertEqual(event.from_ticket_status, QueueTicket.WAITING)
        self.assertEqual(event.to_ticket_status, QueueTicket.SERVING)

        wait_minutes = get_ticket_actual_wait_minutes(ticket)
        self.assertGreaterEqual(wait_minutes, 11.9)
        self.assertLessEqual(wait_minutes, 12.2)

    def test_completion_event_is_appended_after_called_event(self):
        ticket = create_queue_ticket_for_booking(self.booking, actor=self.customer)
        ticket, error = check_in_booking(self.booking, actor=self.customer)
        self.assertIsNone(error)
        counter, error = assign_counter_staff(self.counter, self.staff, actor=self.manager)
        self.assertIsNone(error)
        counter, error = open_counter(counter, actor=self.staff)
        self.assertIsNone(error)
        call_next_ticket(counter, actor=self.staff)
        completed = complete_current_ticket(counter, actor=self.staff)
        self.assertEqual(completed.status, QueueTicket.COMPLETED)

        timeline = list(get_ticket_event_timeline(ticket).values_list("event_type", flat=True))
        self.assertEqual(
            timeline,
            [
                QueueEvent.TICKET_SCHEDULED,
                QueueEvent.CHECKED_IN,
                QueueEvent.CALLED,
                QueueEvent.COMPLETED,
            ],
        )

    def test_counter_lifecycle_history_can_reconstruct_state_changes(self):
        counter, error = assign_counter_staff(self.counter, self.staff, actor=self.manager)
        self.assertIsNone(error)
        counter, error = open_counter(counter, actor=self.staff)
        self.assertIsNone(error)
        counter, error = pause_counter(counter, actor=self.staff)
        self.assertIsNone(error)
        counter, error = resume_counter(counter, actor=self.staff)
        self.assertIsNone(error)
        counter, error = close_counter(counter, actor=self.staff)
        self.assertIsNone(error)

        event_types = list(
            get_counter_event_timeline(counter).values_list("event_type", flat=True)
        )
        self.assertEqual(
            event_types,
            [
                QueueEvent.COUNTER_STAFF_ASSIGNED,
                QueueEvent.COUNTER_OPENED,
                QueueEvent.COUNTER_PAUSED,
                QueueEvent.COUNTER_RESUMED,
                QueueEvent.COUNTER_CLOSED,
            ],
        )

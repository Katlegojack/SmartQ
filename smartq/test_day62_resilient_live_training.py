from datetime import date, datetime, timedelta

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from bookings.models import Booking
from branches.models import Branch
from counters.models import Counter
from queues.models import QueueEvent, QueueTicket
from queues.resilient_day import (
    DEFAULT_CUSTOMERS,
    DEFAULT_NO_SHOWS,
    NO_SHOW_GRACE_MINUTES,
    appointment_slots,
    mark_scheduled_no_show,
    no_show_positions,
    scenario_customer_prefix,
)
from queues.services import call_next_ticket, complete_current_ticket
from queues.waiting_time import calculate_estimated_wait_seconds


class Day62ScenarioShapeTests(TestCase):
    target_date = date(2026, 9, 9)

    @classmethod
    def setUpTestData(cls):
        call_command(
            "seed_resilient_day",
            target_date=cls.target_date.isoformat(),
            customers=DEFAULT_CUSTOMERS,
            no_shows=DEFAULT_NO_SHOWS,
            reset=True,
            verbosity=0,
        )

    def test_110_customer_shape_and_branch_hours(self):
        branch = Branch.objects.get(branch_code="ML01")
        self.assertEqual(branch.opening_time.strftime("%H:%M"), "09:00")
        self.assertEqual(branch.closing_time.strftime("%H:%M"), "18:00")

        prefix = scenario_customer_prefix(self.target_date)
        bookings = Booking.objects.filter(
            user__username__startswith=prefix,
            booking_date=self.target_date,
            branch=branch,
        )
        self.assertEqual(bookings.count(), 110)

        tickets = QueueTicket.objects.filter(booking__in=bookings)
        self.assertEqual(tickets.filter(queue_type=QueueTicket.PRIORITY).count(), 11)
        self.assertEqual(tickets.filter(queue_type=QueueTicket.GENERAL).count(), 99)
        self.assertFalse(tickets.exclude(status=QueueTicket.SCHEDULED).exists())

        slots = appointment_slots(110)
        self.assertEqual(slots[0].strftime("%H:%M"), "09:00")
        self.assertEqual(slots[-1].strftime("%H:%M"), "17:45")

    def test_no_show_selection_is_exact_and_reproducible(self):
        first = no_show_positions(110, self.target_date, 10)
        second = no_show_positions(110, self.target_date, 10)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 10)
        self.assertFalse(first.intersection({0, 1, 2}))

    def test_scheduled_no_show_never_enters_waiting(self):
        prefix = scenario_customer_prefix(self.target_date)
        zero_index = min(no_show_positions(110, self.target_date, 10))
        booking = Booking.objects.select_related("queueticket").get(
            user__username=f"{prefix}{zero_index + 1:03d}"
        )
        occurred_at = timezone.make_aware(
            datetime.combine(self.target_date, booking.booking_time)
        ) + timedelta(minutes=NO_SHOW_GRACE_MINUTES)

        ticket, error = mark_scheduled_no_show(booking, occurred_at=occurred_at)
        self.assertIsNone(error)
        booking.refresh_from_db()
        ticket.refresh_from_db()
        self.assertIsNone(booking.checked_in_at)
        self.assertEqual(booking.status, Booking.NO_SHOW)
        self.assertEqual(ticket.status, QueueTicket.NO_SHOW)
        event = QueueEvent.objects.filter(ticket=ticket, event_type=QueueEvent.NO_SHOW).latest("id")
        self.assertEqual(event.metadata["reason"], "scheduled_absence")
        self.assertEqual(event.metadata["grace_minutes"], 10)


class Day62PriorityOverflowTests(TestCase):
    target_date = date(2026, 9, 9)

    @classmethod
    def setUpTestData(cls):
        call_command(
            "seed_resilient_day",
            target_date=cls.target_date.isoformat(),
            customers=110,
            no_shows=10,
            reset=True,
            verbosity=0,
        )

    def _activate(self, ticket, minutes_ago):
        now = timezone.now()
        booking = ticket.booking
        booking.checked_in_at = now - timedelta(minutes=minutes_ago)
        booking.status = Booking.PENDING
        booking.save(update_fields=["checked_in_at", "status"])
        ticket.status = QueueTicket.WAITING
        ticket.assigned_counter = None
        ticket.save(update_fields=["status", "assigned_counter"])

    def test_priority_counter_helps_general_only_when_priority_is_empty(self):
        branch = Branch.objects.get(branch_code="ML01")
        priority_counter = Counter.objects.get(branch=branch, queue_type=QueueTicket.PRIORITY)
        priority_counter.status = Counter.OPEN
        priority_counter.save(update_fields=["status"])

        prefix = scenario_customer_prefix(self.target_date)
        general = QueueTicket.objects.select_related("booking", "booking__service").filter(
            booking__user__username__startswith=prefix,
            queue_type=QueueTicket.GENERAL,
        ).first()
        self._activate(general, 5)

        called = call_next_ticket(
            priority_counter,
            booking_date=self.target_date,
            actor=priority_counter.assigned_staff,
        )
        self.assertEqual(called.id, general.id)
        called_event = QueueEvent.objects.filter(ticket=called, event_type=QueueEvent.CALLED).latest("id")
        self.assertTrue(called_event.metadata["priority_overflow"])

        complete_current_ticket(priority_counter, actor=priority_counter.assigned_staff)

        priority = QueueTicket.objects.select_related("booking", "booking__service").filter(
            booking__user__username__startswith=prefix,
            queue_type=QueueTicket.PRIORITY,
        ).first()
        second_general = QueueTicket.objects.select_related("booking", "booking__service").filter(
            booking__user__username__startswith=prefix,
            queue_type=QueueTicket.GENERAL,
        ).exclude(pk=general.pk).first()
        self._activate(second_general, 10)
        self._activate(priority, 1)

        called = call_next_ticket(
            priority_counter,
            booking_date=self.target_date,
            actor=priority_counter.assigned_staff,
        )
        self.assertEqual(called.id, priority.id)

    def test_general_eta_can_use_open_priority_capacity(self):
        branch = Branch.objects.get(branch_code="ML01")
        counters = list(Counter.objects.filter(branch=branch).order_by("counter_number"))
        for counter in counters:
            counter.status = Counter.OPEN
            counter.save(update_fields=["status"])

        prefix = scenario_customer_prefix(self.target_date)
        general_tickets = list(
            QueueTicket.objects.select_related("booking", "booking__service")
            .filter(
                booking__user__username__startswith=prefix,
                queue_type=QueueTicket.GENERAL,
            )[:4]
        )
        for index, ticket in enumerate(general_tickets):
            self._activate(ticket, 10 - index)

        target = general_tickets[-1]
        estimate_with_three = calculate_estimated_wait_seconds(target)

        priority_counter = Counter.objects.get(branch=branch, queue_type=QueueTicket.PRIORITY)
        priority_counter.status = Counter.CLOSED
        priority_counter.save(update_fields=["status"])
        estimate_with_two = calculate_estimated_wait_seconds(target)

        self.assertLessEqual(estimate_with_three, estimate_with_two)

from datetime import date, time, timedelta

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from accounts.models import Profile
from bookings.models import Booking
from branches.models import Branch
from counters.models import Counter
from counters.services import open_counter
from queues.busy_day import (
    SCENARIO_BRANCH_CODE,
    SERVICE_PROFILES,
    SERVICE_SEQUENCE,
    appointment_datetime,
    planned_service_minutes,
    scenario_customer_prefix,
)
from queues.models import QueueForecastObservation, QueueTicket
from queues.services import call_next_ticket, complete_current_ticket


class Day61BusyDaySimulationTests(TestCase):
    target_date = date(2026, 9, 7)

    @classmethod
    def setUpTestData(cls):
        call_command(
            "seed_busy_day",
            target_date=cls.target_date.isoformat(),
            customers=80,
            verbosity=0,
        )

    def scenario_bookings(self):
        return Booking.objects.filter(
            user__username__startswith=scenario_customer_prefix(self.target_date),
            booking_date=self.target_date,
        ).select_related("user", "user__profile", "service", "queueticket")

    def test_seed_creates_exact_busy_day_shape(self):
        bookings = self.scenario_bookings()
        self.assertEqual(bookings.count(), 80)

        tickets = QueueTicket.objects.filter(booking__in=bookings)
        self.assertEqual(tickets.filter(queue_type=QueueTicket.GENERAL).count(), 72)
        self.assertEqual(tickets.filter(queue_type=QueueTicket.PRIORITY).count(), 8)

        booking_times = set(bookings.values_list("booking_time", flat=True))
        self.assertIn(time(8, 0), booking_times)
        self.assertIn(time(10, 0), booking_times)
        self.assertIn(time(11, 0), booking_times)
        self.assertIn(time(14, 0), booking_times)
        self.assertIn(time(15, 45), booking_times)

        service_counts = {
            code: bookings.filter(service__service_code=code).count()
            for code in SERVICE_SEQUENCE
        }
        self.assertEqual(sum(service_counts.values()), 80)
        self.assertLessEqual(max(service_counts.values()) - min(service_counts.values()), 1)

        synthetic_users = [booking.user for booking in bookings]
        self.assertTrue(all(not user.has_usable_password() for user in synthetic_users))

    def test_every_service_has_early_exact_and_overrun_examples(self):
        bookings = self.scenario_bookings()
        for service_code in SERVICE_SEQUENCE:
            target = SERVICE_PROFILES[service_code]["average_minutes"]
            values = [
                planned_service_minutes(
                    booking.user.username,
                    service_code,
                    self.target_date,
                )
                for booking in bookings.filter(service__service_code=service_code)
            ]
            with self.subTest(service=service_code):
                self.assertTrue(any(value < target for value in values))
                self.assertIn(target, values)
                self.assertTrue(any(value > target for value in values))

    def test_three_0800_arrivals_keep_two_general_and_one_priority_counter_busy(self):
        branch = Branch.objects.get(branch_code=SCENARIO_BRANCH_CODE)
        counters = list(
            Counter.objects.filter(branch=branch).select_related("assigned_staff").order_by("counter_number")
        )
        self.assertEqual(len(counters), 3)
        self.assertEqual(
            [counter.queue_type for counter in counters],
            [QueueTicket.GENERAL, QueueTicket.GENERAL, QueueTicket.PRIORITY],
        )
        self.assertTrue(
            all(counter.assigned_staff.profile.role == Profile.COUNTER_STAFF for counter in counters)
        )

        for counter in counters:
            opened, error = open_counter(counter, actor=counter.assigned_staff)
            self.assertIsNone(error)
            self.assertEqual(opened.status, Counter.OPEN)

        eight_am = list(
            self.scenario_bookings().filter(booking_time=time(8, 0)).order_by("id")[:3]
        )
        self.assertEqual(len(eight_am), 3)
        for booking in eight_am:
            scheduled_at = appointment_datetime(booking)
            from queues.busy_day import activate_simulation_booking

            ticket, error = activate_simulation_booking(booking, occurred_at=scheduled_at)
            self.assertIsNone(error)
            self.assertEqual(ticket.status, QueueTicket.WAITING)

        called = []
        for counter in counters:
            counter.refresh_from_db()
            ticket = call_next_ticket(
                counter,
                booking_date=self.target_date,
                actor=counter.assigned_staff,
            )
            self.assertIsNotNone(ticket)
            called.append(ticket)

        self.assertEqual(sum(ticket.queue_type == QueueTicket.GENERAL for ticket in called), 2)
        self.assertEqual(sum(ticket.queue_type == QueueTicket.PRIORITY for ticket in called), 1)
        self.assertEqual(
            QueueTicket.objects.filter(
                booking__branch=branch,
                booking__booking_date=self.target_date,
                status=QueueTicket.SERVING,
            ).count(),
            3,
        )
        self.assertEqual(QueueForecastObservation.objects.filter(ticket__in=called).count(), 3)

    def test_completion_keeps_real_service_variance_for_forecasting(self):
        branch = Branch.objects.get(branch_code=SCENARIO_BRANCH_CODE)
        counter = Counter.objects.get(branch=branch, counter_number="1")
        counter, error = open_counter(counter, actor=counter.assigned_staff)
        self.assertIsNone(error)

        booking = (
            self.scenario_bookings()
            .filter(booking_time=time(8, 0), queueticket__queue_type=QueueTicket.GENERAL)
            .first()
        )
        from queues.busy_day import activate_simulation_booking

        activate_simulation_booking(booking, occurred_at=appointment_datetime(booking))
        ticket = call_next_ticket(counter, booking_date=self.target_date, actor=counter.assigned_staff)
        self.assertIsNotNone(ticket)

        planned_minutes = planned_service_minutes(
            ticket.booking.user.username,
            ticket.booking.service.service_code,
            self.target_date,
        )
        ticket.service_started_at = timezone.now() - timedelta(minutes=planned_minutes)
        ticket.save(update_fields=["service_started_at"])

        completed = complete_current_ticket(counter, actor=counter.assigned_staff)
        self.assertEqual(completed.status, QueueTicket.COMPLETED)
        self.assertIsNotNone(completed.actual_service_seconds)
        self.assertIsNotNone(completed.service_variance_seconds)

        observation = QueueForecastObservation.objects.get(ticket=completed)
        self.assertIsNotNone(observation.actual_service_seconds)
        self.assertEqual(
            observation.service_variance_seconds,
            completed.service_variance_seconds,
        )

from datetime import date, datetime, time, timedelta
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from accounts.models import Profile
from bookings.models import Booking
from branches.models import Branch
from counters.models import Counter
from queues.models import QueueEvent, QueueTicket
from queues.services import call_next_ticket, complete_current_ticket
from queues.waiting_time import get_ticket_prediction
from services.models import Service


class Day58RealtimeServiceTimingTests(TestCase):
    """Protect live ETA timing and the service-duration data needed for forecasting."""

    def repo_text(self, path):
        return (Path(__file__).resolve().parents[1] / path).read_text(encoding="utf-8")

    def make_customer(self, username):
        user = User.objects.create_user(username=username, password="SafePassword123!")
        Profile.objects.create(
            user=user,
            date_of_birth=date(1995, 1, 1),
            gender=Profile.OTHER,
            role=Profile.CUSTOMER,
        )
        return user

    def make_booking(self, user, checked_in_at, booking_time):
        return Booking.objects.create(
            user=user,
            branch=self.branch,
            service=self.service,
            booking_date=self.today,
            booking_time=booking_time,
            status=Booking.PENDING,
            checked_in_at=checked_in_at,
        )

    def setUp(self):
        self.today = timezone.localdate()
        self.branch = Branch.objects.create(
            branch_code="D58BARBER",
            name="Day 58 Barber Shop",
            address="58 Live Queue Street",
            city="Pretoria",
            opening_time=time(8, 0),
            closing_time=time(18, 0),
            is_active=True,
        )
        self.service = Service.objects.create(
            service_code="CUT58",
            name="Barber service",
            description="Twenty minute reference service",
            average_service_time=20,
            is_active=True,
        )
        self.counter = Counter.objects.create(
            branch=self.branch,
            counter_number="1",
            queue_type=QueueTicket.GENERAL,
            status=Counter.OPEN,
        )

        tz = timezone.get_current_timezone()
        self.started_at = timezone.make_aware(
            datetime.combine(self.today, time(9, 0)),
            tz,
        )
        self.first_user = self.make_customer("day58_first")
        self.second_user = self.make_customer("day58_second")
        self.first_booking = self.make_booking(
            self.first_user,
            self.started_at - timedelta(minutes=10),
            time(9, 0),
        )
        self.second_booking = self.make_booking(
            self.second_user,
            self.started_at - timedelta(minutes=5),
            time(9, 20),
        )
        self.first_ticket = QueueTicket.objects.create(
            booking=self.first_booking,
            queue_number="A001",
            queue_type=QueueTicket.GENERAL,
            status=QueueTicket.WAITING,
        )
        self.second_ticket = QueueTicket.objects.create(
            booking=self.second_booking,
            queue_number="A002",
            queue_type=QueueTicket.GENERAL,
            status=QueueTicket.WAITING,
        )

    def test_waiting_customer_eta_counts_current_service_and_ticks_down(self):
        with patch("queues.services.timezone.now", return_value=self.started_at):
            called = call_next_ticket(self.counter, booking_date=self.today)

        self.assertEqual(called.id, self.first_ticket.id)
        self.assertEqual(called.service_target_seconds, 20 * 60)
        self.assertEqual(called.service_started_at, self.started_at)

        prediction = get_ticket_prediction(
            self.second_ticket,
            now=self.started_at + timedelta(minutes=5),
        )
        self.assertEqual(prediction["people_ahead"], 1)
        self.assertEqual(prediction["queue_position"], 2)
        self.assertEqual(prediction["estimated_wait_seconds"], 15 * 60)
        self.assertEqual(prediction["estimated_wait_time"], 15)

    def test_serving_customer_gets_live_elapsed_and_target_remaining_clock(self):
        self.first_ticket.status = QueueTicket.SERVING
        self.first_ticket.assigned_counter = self.counter
        self.first_ticket.service_started_at = self.started_at
        self.first_ticket.service_target_seconds = 20 * 60
        self.first_ticket.save(
            update_fields=[
                "status",
                "assigned_counter",
                "service_started_at",
                "service_target_seconds",
            ]
        )

        prediction = get_ticket_prediction(
            self.first_ticket,
            now=self.started_at + timedelta(minutes=7, seconds=30),
        )
        self.assertEqual(prediction["estimated_wait_seconds"], 0)
        self.assertEqual(prediction["service_elapsed_seconds"], 450)
        self.assertEqual(prediction["service_remaining_seconds"], 750)
        self.assertEqual(prediction["service_overrun_seconds"], 0)

    def test_completion_keeps_actual_duration_and_saved_time_for_future_models(self):
        with patch("queues.services.timezone.now", return_value=self.started_at):
            call_next_ticket(self.counter, booking_date=self.today)

        completed_at = self.started_at + timedelta(minutes=15)
        with patch("queues.services.timezone.now", return_value=completed_at):
            completed = complete_current_ticket(self.counter)

        completed.refresh_from_db()
        self.assertEqual(completed.status, QueueTicket.COMPLETED)
        self.assertEqual(completed.service_target_seconds, 1200)
        self.assertEqual(completed.actual_service_seconds, 900)
        self.assertEqual(completed.service_variance_seconds, -300)
        self.assertEqual(completed.service_completed_at, completed_at)

        event = QueueEvent.objects.get(ticket=completed, event_type=QueueEvent.COMPLETED)
        self.assertEqual(event.metadata["service_target_seconds"], 1200)
        self.assertEqual(event.metadata["actual_service_seconds"], 900)
        self.assertEqual(event.metadata["service_variance_seconds"], -300)
        self.assertEqual(event.metadata["service_minutes_saved"], 5.0)
        self.assertEqual(event.metadata["service_overrun_minutes"], 0.0)

    def test_idle_parallel_counter_can_make_next_customer_due_now(self):
        Counter.objects.create(
            branch=self.branch,
            counter_number="2",
            queue_type=QueueTicket.GENERAL,
            status=Counter.OPEN,
        )
        self.first_ticket.status = QueueTicket.SERVING
        self.first_ticket.assigned_counter = self.counter
        self.first_ticket.service_started_at = self.started_at
        self.first_ticket.service_target_seconds = 1200
        self.first_ticket.save(
            update_fields=[
                "status",
                "assigned_counter",
                "service_started_at",
                "service_target_seconds",
            ]
        )

        prediction = get_ticket_prediction(
            self.second_ticket,
            now=self.started_at + timedelta(minutes=5),
        )
        self.assertEqual(prediction["people_ahead"], 1)
        self.assertEqual(prediction["estimated_wait_seconds"], 0)

    def test_frontend_displays_minutes_while_internal_timing_stays_second_resolution(self):
        customer = self.repo_text("frontend/src/pages/CustomerPage.tsx")
        counter = self.repo_text("frontend/src/pages/CounterPage.tsx")
        types = self.repo_text("frontend/src/types.ts")

        for source in [customer, counter]:
            self.assertIn("const durationMinutes", source)
            self.assertIn('return "0 min"', source)
            self.assertIn('return "<1 min"', source)
            self.assertIn('return `${Math.max(minutes, 1)} min`', source)
            self.assertNotIn("durationClock", source)
            self.assertNotIn("padStart(2", source)

        for contract in [
            "window.setInterval(() => setClockMs(Date.now()), 1_000)",
            "refetchInterval: 2_000",
            'Metric label="Estimated wait"',
            'Metric label="Service elapsed"',
            'Metric label="Target remaining"',
            "estimated_wait_seconds",
        ]:
            self.assertIn(contract, customer)

        self.assertIn('Elapsed {durationMinutes(liveServiceElapsedSeconds, "elapsed")}', counter)
        self.assertIn("Target remaining {durationMinutes(serviceRemainingSeconds)}", counter)

        for contract in [
            "service_started_at",
            "service_target_seconds",
            "actual_service_seconds",
            "service_variance_seconds",
            "estimated_wait_seconds",
            "prediction_generated_at",
        ]:
            self.assertIn(contract, types)

from concurrent.futures import ThreadPoolExecutor
from datetime import date, time
from unittest import skipUnless

from django.contrib.auth.models import User
from django.db import connection, connections
from django.test import TestCase, TransactionTestCase

from accounts.models import Profile
from bookings.models import Booking
from branches.models import Branch
from services.models import Service

from .models import QueueNumberSequence, QueueTicket
from .services import create_queue_ticket_for_booking, generate_queue_number


class QueueNumberSequenceTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(
            branch_code="JHB001",
            name="Johannesburg Branch",
            address="Civic Centre",
            city="Johannesburg",
            opening_time=time(8, 0),
            closing_time=time(16, 30),
        )
        self.service = Service.objects.create(
            service_code="ID001",
            name="Identity Service",
            description="Identity document service",
            average_service_time=10,
        )
        self.user = User.objects.create_user(
            username="queue.customer",
            password="Strong-Test-Pass-482!",
        )
        Profile.objects.create(
            user=self.user,
            date_of_birth=date(1995, 1, 1),
            gender=Profile.OTHER,
            role=Profile.CUSTOMER,
        )

    def create_booking(self, *, booking_date=None, booking_time=None):
        return Booking.objects.create(
            user=self.user,
            branch=self.branch,
            service=self.service,
            booking_date=booking_date or date(2026, 9, 2),
            booking_time=booking_time or time(9, 0),
            status=Booking.PENDING,
            source=Booking.ONLINE,
        )

    def test_ticket_creation_advances_database_sequence(self):
        first_booking = self.create_booking(booking_time=time(9, 0))
        second_booking = self.create_booking(booking_time=time(9, 10))

        first_ticket = create_queue_ticket_for_booking(first_booking)
        second_ticket = create_queue_ticket_for_booking(second_booking)

        self.assertEqual(first_ticket.queue_number, "A001")
        self.assertEqual(second_ticket.queue_number, "A002")
        sequence = QueueNumberSequence.objects.get(
            branch=self.branch,
            booking_date=first_booking.booking_date,
            queue_type=QueueTicket.GENERAL,
        )
        self.assertEqual(sequence.last_number, 2)

    def test_sequence_scope_resets_for_a_different_booking_date(self):
        first_booking = self.create_booking(booking_date=date(2026, 9, 2))
        next_day_booking = self.create_booking(booking_date=date(2026, 9, 3))

        first_ticket = create_queue_ticket_for_booking(first_booking)
        next_day_ticket = create_queue_ticket_for_booking(next_day_booking)

        self.assertEqual(first_ticket.queue_number, "A001")
        self.assertEqual(next_day_ticket.queue_number, "A001")
        self.assertEqual(QueueNumberSequence.objects.count(), 2)

    def test_general_and_priority_sequences_are_independent(self):
        general_booking = self.create_booking(booking_time=time(9, 0))
        priority_booking = self.create_booking(booking_time=time(9, 10))

        general_number = generate_queue_number(general_booking, QueueTicket.GENERAL)
        priority_number = generate_queue_number(priority_booking, QueueTicket.PRIORITY)

        self.assertEqual(general_number, "A001")
        self.assertEqual(priority_number, "P001")
        self.assertEqual(QueueNumberSequence.objects.count(), 2)

    def test_existing_sequence_state_is_respected(self):
        booking = self.create_booking()
        QueueNumberSequence.objects.create(
            branch=self.branch,
            booking_date=booking.booking_date,
            queue_type=QueueTicket.GENERAL,
            last_number=7,
        )

        queue_number = generate_queue_number(booking, QueueTicket.GENERAL)

        self.assertEqual(queue_number, "A008")

    def test_missing_sequence_is_seeded_from_existing_ticket_history(self):
        historical_booking = self.create_booking(booking_time=time(9, 0))
        new_booking = self.create_booking(booking_time=time(9, 10))
        QueueTicket.objects.create(
            booking=historical_booking,
            queue_number="A007",
            queue_type=QueueTicket.GENERAL,
            status=QueueTicket.SCHEDULED,
        )

        queue_number = generate_queue_number(new_booking, QueueTicket.GENERAL)

        self.assertEqual(queue_number, "A008")
        sequence = QueueNumberSequence.objects.get(
            branch=self.branch,
            booking_date=new_booking.booking_date,
            queue_type=QueueTicket.GENERAL,
        )
        self.assertEqual(sequence.last_number, 8)


@skipUnless(
    connection.vendor == "postgresql",
    "Concurrent row-lock verification requires PostgreSQL.",
)
class PostgreSQLQueueNumberConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.branch = Branch.objects.create(
            branch_code="JHB001",
            name="Johannesburg Branch",
            address="Civic Centre",
            city="Johannesburg",
            opening_time=time(8, 0),
            closing_time=time(16, 30),
        )
        self.service = Service.objects.create(
            service_code="ID001",
            name="Identity Service",
            description="Identity document service",
            average_service_time=10,
        )
        self.user = User.objects.create_user(
            username="concurrency.customer",
            password="Strong-Test-Pass-482!",
        )
        Profile.objects.create(
            user=self.user,
            date_of_birth=date(1995, 1, 1),
            gender=Profile.OTHER,
            role=Profile.CUSTOMER,
        )
        self.booking_ids = [
            Booking.objects.create(
                user=self.user,
                branch=self.branch,
                service=self.service,
                booking_date=date(2026, 9, 2),
                booking_time=time(9, 0) if index == 0 else time(9, 10),
                status=Booking.PENDING,
                source=Booking.ONLINE,
            ).pk
            for index in range(2)
        ]

    def allocate_number(self, booking_id):
        thread_connection = connections["default"]
        thread_connection.close()
        try:
            booking = Booking.objects.select_related("branch").get(pk=booking_id)
            return generate_queue_number(booking, QueueTicket.GENERAL)
        finally:
            # CONN_MAX_AGE is non-zero in the production profile, so
            # close_old_connections() may intentionally retain this connection.
            # Threaded tests must close it explicitly before Django drops test DB.
            thread_connection.close()

    def test_concurrent_requests_receive_distinct_numbers(self):
        with ThreadPoolExecutor(max_workers=2) as executor:
            numbers = list(executor.map(self.allocate_number, self.booking_ids))

        self.assertEqual(set(numbers), {"A001", "A002"})
        sequence = QueueNumberSequence.objects.get(
            branch=self.branch,
            booking_date=date(2026, 9, 2),
            queue_type=QueueTicket.GENERAL,
        )
        self.assertEqual(sequence.last_number, 2)

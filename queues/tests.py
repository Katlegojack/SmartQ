from datetime import date, time, timedelta

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounts.models import Profile
from bookings.models import Booking
from branches.models import Branch
from counters.models import Counter
from services.models import Service
from .models import QueueTicket


class QueueOperationalAPITests(APITestCase):
    """Regression tests for the Day 28 operational queue workflow."""

    def setUp(self):
        self.branch = Branch.objects.create(
            branch_code="KIM01",
            name="Kimberley Branch",
            address="1 Test Street",
            city="Kimberley",
            opening_time=time(8, 0),
            closing_time=time(16, 30),
            is_active=True,
        )
        self.service = Service.objects.create(
            service_code="ID01",
            name="ID Application",
            description="Identity document service",
            average_service_time=10,
            is_active=True,
        )

        self.customer = User.objects.create_user(
            username="customer",
            password="test-password",
        )
        Profile.objects.create(
            user=self.customer,
            date_of_birth=date(1995, 1, 1),
            gender=Profile.MALE,
            disability_status=False,
        )

        self.staff = User.objects.create_user(
            username="staff",
            password="test-password",
            is_staff=True,
        )
        Profile.objects.create(
            user=self.staff,
            date_of_birth=date(1990, 1, 1),
            gender=Profile.OTHER,
            disability_status=False,
        )

        self.booking = Booking.objects.create(
            user=self.customer,
            branch=self.branch,
            service=self.service,
            booking_date=date.today(),
            booking_time=time(9, 0),
            status=Booking.PENDING,
        )
        self.ticket = QueueTicket.objects.create(
            booking=self.booking,
            queue_number="A001",
            queue_type=QueueTicket.GENERAL,
            status=QueueTicket.WAITING,
        )
        self.counter = Counter.objects.create(
            branch=self.branch,
            counter_number="1",
            queue_type=QueueTicket.GENERAL,
            status=Counter.OPEN,
        )
        self.client = APIClient()

    def _put_customer_in_service(self):
        """Reusable test helper that places the default customer at the counter."""
        self.ticket.status = QueueTicket.SERVING
        self.ticket.assigned_counter = self.counter
        self.ticket.save(update_fields=["status", "assigned_counter"])
        self.booking.status = Booking.CONFIRMED
        self.booking.save(update_fields=["status"])

    def test_customer_cannot_operate_staff_counter(self):
        """A normal authenticated customer must not be able to call the queue."""
        self.client.force_authenticate(user=self.customer)

        response = self.client.post(
            reverse("api_call_next_ticket", kwargs={"counter_id": self.counter.id})
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, QueueTicket.WAITING)

    def test_closed_counter_cannot_call_customer(self):
        """A closed counter must be opened before it changes queue state."""
        self.counter.status = Counter.CLOSED
        self.counter.save(update_fields=["status"])
        self.client.force_authenticate(user=self.staff)

        response = self.client.post(
            reverse("api_call_next_ticket", kwargs={"counter_id": self.counter.id})
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, QueueTicket.WAITING)

    def test_staff_can_call_next_and_booking_is_confirmed(self):
        self.client.force_authenticate(user=self.staff)

        response = self.client.post(
            reverse("api_call_next_ticket", kwargs={"counter_id": self.counter.id})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.ticket.refresh_from_db()
        self.booking.refresh_from_db()
        self.assertEqual(self.ticket.status, QueueTicket.SERVING)
        self.assertEqual(self.ticket.assigned_counter, self.counter)
        self.assertEqual(self.booking.status, Booking.CONFIRMED)

    def test_future_booking_is_not_called_early(self):
        """Call Next must operate only on today's live queue."""
        self.booking.booking_date = date.today() + timedelta(days=1)
        self.booking.save(update_fields=["booking_date"])
        self.client.force_authenticate(user=self.staff)

        response = self.client.post(
            reverse("api_call_next_ticket", kwargs={"counter_id": self.counter.id})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, QueueTicket.WAITING)
        self.assertIsNone(self.ticket.assigned_counter)

    def test_counter_cannot_call_second_customer_while_busy(self):
        """A counter serving someone must not accidentally serve two tickets."""
        self._put_customer_in_service()

        second_user = User.objects.create_user(username="customer2", password="pw")
        Profile.objects.create(
            user=second_user,
            date_of_birth=date(1998, 1, 1),
            gender=Profile.OTHER,
            disability_status=False,
        )
        second_booking = Booking.objects.create(
            user=second_user,
            branch=self.branch,
            service=self.service,
            booking_date=date.today(),
            booking_time=time(9, 30),
            status=Booking.PENDING,
        )
        second_ticket = QueueTicket.objects.create(
            booking=second_booking,
            queue_number="A002",
            queue_type=QueueTicket.GENERAL,
            status=QueueTicket.WAITING,
        )

        self.client.force_authenticate(user=self.staff)
        response = self.client.post(
            reverse("api_call_next_ticket", kwargs={"counter_id": self.counter.id})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        second_ticket.refresh_from_db()
        self.assertEqual(second_ticket.status, QueueTicket.WAITING)
        self.assertIsNone(second_ticket.assigned_counter)

    def test_complete_ticket_updates_booking_and_releases_counter(self):
        self._put_customer_in_service()

        self.client.force_authenticate(user=self.staff)
        response = self.client.post(
            reverse("api_complete_current_ticket", kwargs={"counter_id": self.counter.id})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.ticket.refresh_from_db()
        self.booking.refresh_from_db()
        self.assertEqual(self.ticket.status, QueueTicket.COMPLETED)
        self.assertIsNone(self.ticket.assigned_counter)
        self.assertEqual(self.booking.status, Booking.COMPLETED)

    def test_no_show_updates_booking_and_releases_counter(self):
        """No-show must update both domain objects and free the counter."""
        self._put_customer_in_service()

        self.client.force_authenticate(user=self.staff)
        response = self.client.post(
            reverse("api_no_show_current_ticket", kwargs={"counter_id": self.counter.id})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.ticket.refresh_from_db()
        self.booking.refresh_from_db()
        self.assertEqual(self.ticket.status, QueueTicket.NO_SHOW)
        self.assertIsNone(self.ticket.assigned_counter)
        self.assertEqual(self.booking.status, Booking.NO_SHOW)

    def test_staff_can_read_current_counter_ticket(self):
        self._put_customer_in_service()
        self.client.force_authenticate(user=self.staff)

        response = self.client.get(
            reverse("api_current_counter_ticket", kwargs={"counter_id": self.counter.id})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["queue_number"], "A001")
        self.assertEqual(response.data["status"], QueueTicket.SERVING)

    def test_customer_can_read_own_current_queue_prediction(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.get(reverse("api_my_current_queue_ticket"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["ticket"]["queue_number"], "A001")
        self.assertIn("prediction", response.data)
        self.assertEqual(response.data["prediction"]["queue_position"], 1)

    def test_waiting_queue_places_priority_before_general(self):
        """Combined waiting-room views must make the intended priority visible."""
        priority_user = User.objects.create_user(username="priority", password="pw")
        Profile.objects.create(
            user=priority_user,
            date_of_birth=date(1960, 1, 1),
            gender=Profile.OTHER,
            disability_status=False,
        )
        priority_booking = Booking.objects.create(
            user=priority_user,
            branch=self.branch,
            service=self.service,
            booking_date=date.today(),
            booking_time=time(9, 15),
            status=Booking.PENDING,
        )
        QueueTicket.objects.create(
            booking=priority_booking,
            queue_number="P001",
            queue_type=QueueTicket.PRIORITY,
            status=QueueTicket.WAITING,
        )

        self.client.force_authenticate(user=self.staff)
        response = self.client.get(
            reverse("api_branch_waiting_queue", kwargs={"branch_id": self.branch.id})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]["queue_type"], QueueTicket.PRIORITY)
        self.assertEqual(response.data[0]["queue_number"], "P001")

    def test_waiting_queue_rejects_invalid_queue_type(self):
        self.client.force_authenticate(user=self.staff)

        response = self.client.get(
            reverse("api_branch_waiting_queue", kwargs={"branch_id": self.branch.id}),
            {"queue_type": "vip"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

from datetime import date, time

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

    def test_customer_cannot_operate_staff_counter(self):
        """A normal authenticated customer must not be able to call the queue."""
        self.client.force_authenticate(user=self.customer)

        response = self.client.post(
            reverse("api_call_next_ticket", kwargs={"counter_id": self.counter.id})
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
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

    def test_complete_ticket_updates_booking_and_releases_counter(self):
        self.ticket.status = QueueTicket.SERVING
        self.ticket.assigned_counter = self.counter
        self.ticket.save(update_fields=["status", "assigned_counter"])
        self.booking.status = Booking.CONFIRMED
        self.booking.save(update_fields=["status"])

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

    def test_customer_can_read_own_current_queue_prediction(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.get(reverse("api_my_current_queue_ticket"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["ticket"]["queue_number"], "A001")
        self.assertIn("prediction", response.data)
        self.assertEqual(response.data["prediction"]["queue_position"], 1)

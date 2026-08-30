from datetime import date, time, timedelta

from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounts.models import Profile
from branches.models import Branch
from queues.models import QueueTicket
from services.models import Service
from .models import Booking


class BookingCheckInAPITests(APITestCase):
    """Regression tests for the Day 30 arrival/check-in workflow."""

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
        self.other_branch = Branch.objects.create(
            branch_code="PTA01",
            name="Pretoria Branch",
            address="2 Test Street",
            city="Pretoria",
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

        self.customer = User.objects.create_user(username="customer", password="pw")
        Profile.objects.create(
            user=self.customer,
            date_of_birth=date(1995, 1, 1),
            gender=Profile.OTHER,
            role=Profile.CUSTOMER,
        )

        self.booking = Booking.objects.create(
            user=self.customer,
            branch=self.branch,
            service=self.service,
            booking_date=timezone.localdate(),
            booking_time=time(9, 0),
            status=Booking.PENDING,
        )
        self.ticket = QueueTicket.objects.create(
            booking=self.booking,
            queue_number="A001",
            queue_type=QueueTicket.GENERAL,
            status=QueueTicket.SCHEDULED,
        )
        self.client = APIClient()

    def test_customer_can_check_in_own_booking_today(self):
        self.client.force_authenticate(user=self.customer)
        response = self.client.post(
            reverse("api_booking_check_in", kwargs={"pk": self.booking.id})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.booking.refresh_from_db()
        self.ticket.refresh_from_db()
        self.assertIsNotNone(self.booking.checked_in_at)
        self.assertEqual(self.ticket.status, QueueTicket.WAITING)
        self.assertTrue(response.data["is_checked_in"])

    def test_customer_cannot_check_in_future_booking(self):
        self.booking.booking_date = timezone.localdate() + timedelta(days=1)
        self.booking.save(update_fields=["booking_date"])
        self.client.force_authenticate(user=self.customer)

        response = self.client.post(
            reverse("api_booking_check_in", kwargs={"pk": self.booking.id})
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, QueueTicket.SCHEDULED)

    def test_customer_cannot_check_in_another_customers_booking(self):
        other = User.objects.create_user(username="other", password="pw")
        Profile.objects.create(
            user=other,
            date_of_birth=date(1990, 1, 1),
            gender=Profile.OTHER,
            role=Profile.CUSTOMER,
        )
        self.client.force_authenticate(user=other)

        response = self.client.post(
            reverse("api_booking_check_in", kwargs={"pk": self.booking.id})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_duplicate_check_in_returns_conflict(self):
        self.client.force_authenticate(user=self.customer)
        first = self.client.post(
            reverse("api_booking_check_in", kwargs={"pk": self.booking.id})
        )
        second = self.client.post(
            reverse("api_booking_check_in", kwargs={"pk": self.booking.id})
        )

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_409_CONFLICT)

    def test_cancelled_booking_cannot_check_in(self):
        self.booking.status = Booking.CANCELLED
        self.booking.save(update_fields=["status"])
        self.ticket.status = QueueTicket.CANCELLED
        self.ticket.save(update_fields=["status"])
        self.client.force_authenticate(user=self.customer)

        response = self.client.post(
            reverse("api_booking_check_in", kwargs={"pk": self.booking.id})
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_receptionist_can_check_in_booking_at_assigned_branch(self):
        receptionist = User.objects.create_user(username="reception", password="pw")
        Profile.objects.create(
            user=receptionist,
            date_of_birth=date(1990, 1, 1),
            gender=Profile.OTHER,
            role=Profile.RECEPTIONIST,
            branch=self.branch,
        )
        self.client.force_authenticate(user=receptionist)

        response = self.client.post(
            reverse("api_staff_booking_check_in", kwargs={"pk": self.booking.id})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.booking.refresh_from_db()
        self.assertIsNotNone(self.booking.checked_in_at)

    def test_receptionist_cannot_check_in_other_branch_booking(self):
        receptionist = User.objects.create_user(username="reception2", password="pw")
        Profile.objects.create(
            user=receptionist,
            date_of_birth=date(1990, 1, 1),
            gender=Profile.OTHER,
            role=Profile.RECEPTIONIST,
            branch=self.other_branch,
        )
        self.client.force_authenticate(user=receptionist)

        response = self.client.post(
            reverse("api_staff_booking_check_in", kwargs={"pk": self.booking.id})
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_reschedule_clears_existing_check_in_and_returns_ticket_to_scheduled(self):
        self.booking.checked_in_at = timezone.now()
        self.booking.save(update_fields=["checked_in_at"])
        self.ticket.status = QueueTicket.WAITING
        self.ticket.save(update_fields=["status"])
        self.client.force_authenticate(user=self.customer)

        response = self.client.patch(
            reverse("api_booking_reschedule", kwargs={"pk": self.booking.id}),
            {
                "booking_date": str(timezone.localdate() + timedelta(days=1)),
                "booking_time": "10:00:00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.booking.refresh_from_db()
        self.ticket.refresh_from_db()
        self.assertIsNone(self.booking.checked_in_at)
        self.assertEqual(self.ticket.status, QueueTicket.SCHEDULED)

    def test_booking_creation_api_creates_scheduled_ticket_not_live_waiting_ticket(self):
        self.client.force_authenticate(user=self.customer)
        response = self.client.post(
            reverse("api_booking_create"),
            {
                "branch": self.branch.id,
                "service": self.service.id,
                "booking_date": str(timezone.localdate() + timedelta(days=2)),
                "booking_time": "11:00:00",
                "is_pregnant": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = Booking.objects.get(pk=response.data["id"])
        ticket = created.queueticket
        self.assertIsNone(created.checked_in_at)
        self.assertEqual(ticket.status, QueueTicket.SCHEDULED)

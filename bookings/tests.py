from datetime import date, datetime, time, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounts.models import Profile
from branches.models import Branch
from queues.models import QueueTicket
from services.models import Service
from .models import Booking, GuestCustomer


class BookingCheckInAPITests(APITestCase):
    """Regression tests for online/in-person live-queue activation."""

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
            booking_time=time(15, 0),
            status=Booking.PENDING,
            source=Booking.ONLINE,
        )
        self.ticket = QueueTicket.objects.create(
            booking=self.booking,
            queue_number="A001",
            queue_type=QueueTicket.GENERAL,
            status=QueueTicket.SCHEDULED,
        )
        self.client = APIClient()

    def _aware_today(self, hour, minute=0):
        value = datetime.combine(timezone.localdate(), time(hour, minute))
        return timezone.make_aware(value, timezone.get_current_timezone())

    def test_customer_can_check_in_from_six_hours_before_appointment(self):
        self.client.force_authenticate(user=self.customer)

        with patch("queues.services.timezone.now", return_value=self._aware_today(9, 0)):
            response = self.client.post(
                reverse("api_booking_check_in", kwargs={"pk": self.booking.id})
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.booking.refresh_from_db()
        self.ticket.refresh_from_db()
        self.assertIsNotNone(self.booking.checked_in_at)
        self.assertEqual(self.ticket.status, QueueTicket.WAITING)
        self.assertTrue(response.data["is_checked_in"])

    def test_customer_cannot_check_in_before_six_hour_window(self):
        self.client.force_authenticate(user=self.customer)

        with patch("queues.services.timezone.now", return_value=self._aware_today(8, 59)):
            response = self.client.post(
                reverse("api_booking_check_in", kwargs={"pk": self.booking.id})
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("check_in_opens_at", response.data)
        self.ticket.refresh_from_db()
        self.booking.refresh_from_db()
        self.assertEqual(self.ticket.status, QueueTicket.SCHEDULED)
        self.assertIsNone(self.booking.checked_in_at)

    def test_unchecked_booking_is_cancelled_after_appointment_time(self):
        self.client.force_authenticate(user=self.customer)

        with patch("queues.services.timezone.now", return_value=self._aware_today(15, 1)):
            response = self.client.post(
                reverse("api_booking_check_in", kwargs={"pk": self.booking.id})
            )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.booking.refresh_from_db()
        self.ticket.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.CANCELLED)
        self.assertEqual(self.ticket.status, QueueTicket.CANCELLED)
        self.assertIsNone(self.booking.checked_in_at)

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

        with patch("queues.services.timezone.now", return_value=self._aware_today(10, 0)):
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

    def test_receptionist_can_check_in_booking_during_window(self):
        receptionist = User.objects.create_user(username="reception", password="pw")
        Profile.objects.create(
            user=receptionist,
            date_of_birth=date(1990, 1, 1),
            gender=Profile.OTHER,
            role=Profile.RECEPTIONIST,
            branch=self.branch,
        )
        self.client.force_authenticate(user=receptionist)

        with patch("queues.services.timezone.now", return_value=self._aware_today(10, 0)):
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

    def test_reschedule_clears_check_in_and_returns_ticket_to_scheduled(self):
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

    def test_online_booking_creation_creates_scheduled_ticket(self):
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
        self.assertEqual(created.source, Booking.ONLINE)
        self.assertIsNone(created.checked_in_at)
        self.assertEqual(ticket.status, QueueTicket.SCHEDULED)


class ReceptionWorkflowAPITests(APITestCase):
    """Reception search and no-account guest walk-in regression coverage."""

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
        self.receptionist = User.objects.create_user(username="reception", password="pw")
        Profile.objects.create(
            user=self.receptionist,
            date_of_birth=date(1990, 1, 1),
            gender=Profile.OTHER,
            role=Profile.RECEPTIONIST,
            branch=self.branch,
        )
        self.customer = User.objects.create_user(
            username="katlego.customer",
            first_name="Katlego",
            last_name="Customer",
            password="pw",
        )
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
            booking_time=time(15, 0),
            source=Booking.ONLINE,
        )
        QueueTicket.objects.create(
            booking=self.booking,
            queue_number="A001",
            queue_type=QueueTicket.GENERAL,
            status=QueueTicket.SCHEDULED,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.receptionist)

    def test_reception_can_search_assigned_branch_booking(self):
        response = self.client.get(
            reverse("api_reception_booking_search"),
            {"q": "Katlego"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.booking.id)

    def test_reception_search_does_not_cross_branch_boundary(self):
        other_user = User.objects.create_user(
            username="katlego.other",
            first_name="Katlego",
            password="pw",
        )
        Profile.objects.create(
            user=other_user,
            date_of_birth=date(1995, 1, 1),
            gender=Profile.OTHER,
            role=Profile.CUSTOMER,
        )
        Booking.objects.create(
            user=other_user,
            branch=self.other_branch,
            service=self.service,
            booking_date=timezone.localdate(),
            booking_time=time(15, 0),
        )

        response = self.client.get(
            reverse("api_reception_booking_search"),
            {"q": "Katlego"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.booking.id)

    def test_reception_can_create_guest_walk_in_without_account(self):
        response = self.client.post(
            reverse("api_reception_guest_walk_in"),
            {
                "full_name": "Guest Person",
                "phone_number": "0712345678",
                "date_of_birth": "1994-04-10",
                "gender": Profile.OTHER,
                "disability_status": False,
                "is_pregnant": False,
                "service": self.service.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        booking = Booking.objects.get(pk=response.data["id"])
        self.assertIsNone(booking.user)
        self.assertIsInstance(booking.guest_customer, GuestCustomer)
        self.assertEqual(booking.source, Booking.WALK_IN)
        self.assertIsNotNone(booking.checked_in_at)
        self.assertEqual(booking.queueticket.status, QueueTicket.WAITING)
        self.assertEqual(response.data["customer_name"], "Guest Person")

    def test_guest_walk_in_receives_priority_when_eligible(self):
        response = self.client.post(
            reverse("api_reception_guest_walk_in"),
            {
                "full_name": "Older Guest",
                "date_of_birth": "1950-01-01",
                "gender": Profile.OTHER,
                "service": self.service.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        booking = Booking.objects.get(pk=response.data["id"])
        self.assertEqual(booking.queueticket.queue_type, QueueTicket.PRIORITY)
        self.assertTrue(booking.queueticket.queue_number.startswith("P"))

    def test_customer_role_cannot_create_guest_walk_in(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.post(
            reverse("api_reception_guest_walk_in"),
            {
                "full_name": "Guest Person",
                "date_of_birth": "1994-04-10",
                "gender": Profile.OTHER,
                "service": self.service.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

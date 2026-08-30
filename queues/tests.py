from datetime import date, time, timedelta

from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounts.models import Profile
from bookings.models import Booking
from branches.models import Branch
from counters.models import Counter
from services.models import Service
from .models import QueueTicket


class QueueOperationalAPITests(APITestCase):
    """Regression tests for live queue operations, authorization, and check-in."""

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

        self.customer = User.objects.create_user(username="customer", password="test-password")
        Profile.objects.create(
            user=self.customer,
            date_of_birth=date(1995, 1, 1),
            gender=Profile.MALE,
            disability_status=False,
            role=Profile.CUSTOMER,
        )

        self.staff = User.objects.create_user(username="staff", password="test-password")
        Profile.objects.create(
            user=self.staff,
            date_of_birth=date(1990, 1, 1),
            gender=Profile.OTHER,
            disability_status=False,
            role=Profile.COUNTER_STAFF,
            branch=self.branch,
        )

        self.booking = Booking.objects.create(
            user=self.customer,
            branch=self.branch,
            service=self.service,
            booking_date=timezone.localdate(),
            booking_time=time(9, 0),
            status=Booking.PENDING,
            checked_in_at=timezone.now(),
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
        self.ticket.status = QueueTicket.SERVING
        self.ticket.assigned_counter = self.counter
        self.ticket.save(update_fields=["status", "assigned_counter"])
        self.booking.status = Booking.CONFIRMED
        self.booking.save(update_fields=["status"])

    def test_customer_cannot_operate_staff_counter(self):
        self.client.force_authenticate(user=self.customer)
        response = self.client.post(
            reverse("api_call_next_ticket", kwargs={"counter_id": self.counter.id})
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_receptionist_can_view_queue_but_cannot_operate_counter(self):
        receptionist = User.objects.create_user(username="reception", password="pw")
        Profile.objects.create(
            user=receptionist,
            date_of_birth=date(1992, 1, 1),
            gender=Profile.OTHER,
            role=Profile.RECEPTIONIST,
            branch=self.branch,
        )
        self.client.force_authenticate(user=receptionist)
        read_response = self.client.get(
            reverse("api_branch_waiting_queue", kwargs={"branch_id": self.branch.id})
        )
        operate_response = self.client.post(
            reverse("api_call_next_ticket", kwargs={"counter_id": self.counter.id})
        )
        self.assertEqual(read_response.status_code, status.HTTP_200_OK)
        self.assertEqual(operate_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_branch_staff_cannot_operate_another_branch(self):
        other_staff = User.objects.create_user(username="otherstaff", password="pw")
        Profile.objects.create(
            user=other_staff,
            date_of_birth=date(1990, 1, 1),
            gender=Profile.OTHER,
            role=Profile.COUNTER_STAFF,
            branch=self.other_branch,
        )
        self.client.force_authenticate(user=other_staff)
        response = self.client.post(
            reverse("api_call_next_ticket", kwargs={"counter_id": self.counter.id})
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_system_admin_can_access_any_branch(self):
        admin_user = User.objects.create_user(username="sysadmin", password="pw")
        Profile.objects.create(
            user=admin_user,
            date_of_birth=date(1985, 1, 1),
            gender=Profile.OTHER,
            role=Profile.SYSTEM_ADMIN,
            branch=None,
        )
        self.client.force_authenticate(user=admin_user)
        response = self.client.get(
            reverse("api_branch_waiting_queue", kwargs={"branch_id": self.branch.id})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_closed_counter_cannot_call_customer(self):
        self.counter.status = Counter.CLOSED
        self.counter.save(update_fields=["status"])
        self.client.force_authenticate(user=self.staff)
        response = self.client.post(
            reverse("api_call_next_ticket", kwargs={"counter_id": self.counter.id})
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

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

    def test_scheduled_customer_is_not_called_before_check_in(self):
        """A same-day appointment must not enter the live queue just because it exists."""
        self.booking.checked_in_at = None
        self.booking.save(update_fields=["checked_in_at"])
        self.ticket.status = QueueTicket.SCHEDULED
        self.ticket.save(update_fields=["status"])
        self.client.force_authenticate(user=self.staff)

        response = self.client.post(
            reverse("api_call_next_ticket", kwargs={"counter_id": self.counter.id})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, QueueTicket.SCHEDULED)

    def test_future_booking_is_not_called_early(self):
        self.booking.booking_date = timezone.localdate() + timedelta(days=1)
        self.booking.save(update_fields=["booking_date"])
        self.client.force_authenticate(user=self.staff)
        response = self.client.post(
            reverse("api_call_next_ticket", kwargs={"counter_id": self.counter.id})
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_counter_cannot_call_second_customer_while_busy(self):
        self._put_customer_in_service()
        second_user = User.objects.create_user(username="customer2", password="pw")
        Profile.objects.create(
            user=second_user,
            date_of_birth=date(1998, 1, 1),
            gender=Profile.OTHER,
            role=Profile.CUSTOMER,
        )
        second_booking = Booking.objects.create(
            user=second_user,
            branch=self.branch,
            service=self.service,
            booking_date=timezone.localdate(),
            booking_time=time(9, 30),
            status=Booking.PENDING,
            checked_in_at=timezone.now(),
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

    def test_customer_can_read_own_current_queue_prediction(self):
        self.client.force_authenticate(user=self.customer)
        response = self.client.get(reverse("api_my_current_queue_ticket"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["ticket"]["queue_number"], "A001")
        self.assertEqual(response.data["prediction"]["queue_position"], 1)

    def test_waiting_queue_places_priority_before_general(self):
        priority_user = User.objects.create_user(username="priority", password="pw")
        Profile.objects.create(
            user=priority_user,
            date_of_birth=date(1960, 1, 1),
            gender=Profile.OTHER,
            role=Profile.CUSTOMER,
        )
        priority_booking = Booking.objects.create(
            user=priority_user,
            branch=self.branch,
            service=self.service,
            booking_date=timezone.localdate(),
            booking_time=time(9, 15),
            status=Booking.PENDING,
            checked_in_at=timezone.now(),
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

    def test_waiting_queue_rejects_invalid_queue_type(self):
        self.client.force_authenticate(user=self.staff)
        response = self.client.get(
            reverse("api_branch_waiting_queue", kwargs={"branch_id": self.branch.id}),
            {"queue_type": "vip"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

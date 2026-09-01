from datetime import date, time, timedelta

from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Profile
from bookings.models import Booking
from branches.models import Branch
from counters.models import Counter
from services.models import BranchService, Service

from .models import QueueEvent, QueueTicket
from .waiting_time import get_ticket_prediction


class Day40FinalBackendAuditTests(APITestCase):
    """Final cross-feature regression and security coverage for backend v1."""

    def setUp(self):
        self.branch = self._branch("PTA01", "Pretoria Branch")
        self.other_branch = self._branch("JHB01", "Johannesburg Branch")
        self.service = Service.objects.create(
            service_code="ID01",
            name="ID Application",
            description="Identity service",
            average_service_time=10,
            is_active=True,
        )
        BranchService.objects.create(
            branch=self.branch,
            service=self.service,
            max_bookings_per_slot=1,
        )
        BranchService.objects.create(
            branch=self.other_branch,
            service=self.service,
            max_bookings_per_slot=1,
        )

        self.customer = self._user("customer", Profile.CUSTOMER)
        self.other_customer = self._user("other_customer", Profile.CUSTOMER)
        self.manager = self._user("manager", Profile.BRANCH_MANAGER, self.branch)
        self.other_manager = self._user(
            "other_manager", Profile.BRANCH_MANAGER, self.other_branch
        )
        self.counter_staff = self._user(
            "counter_staff", Profile.COUNTER_STAFF, self.branch
        )
        self.other_staff = self._user(
            "other_staff", Profile.COUNTER_STAFF, self.branch
        )
        self.admin = self._user("admin", Profile.SYSTEM_ADMIN)

        self.counter = Counter.objects.create(
            branch=self.branch,
            counter_number="1",
            queue_type=QueueTicket.GENERAL,
            assigned_staff=self.counter_staff,
            status=Counter.OPEN,
        )

    def _branch(self, code, name):
        return Branch.objects.create(
            branch_code=code,
            name=name,
            address="1 Main Street",
            city=name.split()[0],
            opening_time=time(8, 0),
            closing_time=time(17, 0),
            is_active=True,
        )

    def _user(self, username, role, branch=None):
        user = User.objects.create_user(username=username, password="pw")
        Profile.objects.create(
            user=user,
            date_of_birth=date(1990, 1, 1),
            gender=Profile.OTHER,
            role=role,
            branch=branch,
        )
        return user

    def _booking_ticket(
        self,
        *,
        user=None,
        branch=None,
        queue_number="A001",
        status=QueueTicket.WAITING,
        checked_in=True,
    ):
        booking = Booking.objects.create(
            user=user or self.customer,
            branch=branch or self.branch,
            service=self.service,
            booking_date=timezone.localdate(),
            booking_time=time(15, 0),
            status=Booking.PENDING,
            source=Booking.ONLINE,
            checked_in_at=timezone.now() if checked_in else None,
        )
        ticket = QueueTicket.objects.create(
            booking=booking,
            queue_number=queue_number,
            queue_type=QueueTicket.GENERAL,
            status=status,
        )
        return booking, ticket

    def test_customer_cannot_read_another_customers_booking_timeline(self):
        booking, _ = self._booking_ticket(user=self.customer, checked_in=False)

        self.client.force_authenticate(self.other_customer)
        response = self.client.get(
            reverse("api_customer_booking_timeline", args=[booking.id])
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_duplicate_check_in_does_not_duplicate_activation_event(self):
        booking, ticket = self._booking_ticket(
            user=self.customer,
            status=QueueTicket.SCHEDULED,
            checked_in=False,
        )
        self.client.force_authenticate(self.customer)

        appointment_at = timezone.make_aware(
            timezone.datetime.combine(timezone.localdate(), booking.booking_time),
            timezone.get_current_timezone(),
        )
        allowed_now = appointment_at - timedelta(hours=1)

        from unittest.mock import patch

        with patch("queues.services.timezone.now", return_value=allowed_now):
            first = self.client.post(reverse("api_booking_check_in", args=[booking.id]))
            second = self.client.post(reverse("api_booking_check_in", args=[booking.id]))

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(
            QueueEvent.objects.filter(
                booking=booking,
                event_type=QueueEvent.CHECKED_IN,
            ).count(),
            1,
        )
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, QueueTicket.WAITING)

    def test_stale_capacity_is_revalidated_before_second_booking_write(self):
        booking_date = timezone.localdate() + timedelta(days=2)
        payload = {
            "branch": self.branch.id,
            "service": self.service.id,
            "booking_date": str(booking_date),
            "booking_time": "08:00:00",
            "is_pregnant": False,
        }

        self.client.force_authenticate(self.customer)
        first = self.client.post(reverse("api_booking_create"), payload, format="json")
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)

        self.client.force_authenticate(self.other_customer)
        second = self.client.post(reverse("api_booking_create"), payload, format="json")

        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            Booking.objects.filter(
                branch=self.branch,
                service=self.service,
                booking_date=booking_date,
                booking_time=time(8, 0),
            ).count(),
            1,
        )

    def test_assigned_counter_staff_can_call_and_complete_one_customer_journey(self):
        booking, ticket = self._booking_ticket()
        self.client.force_authenticate(self.counter_staff)

        called = self.client.post(
            reverse("api_call_next_ticket", args=[self.counter.id])
        )
        self.assertEqual(called.status_code, status.HTTP_200_OK)
        ticket.refresh_from_db()
        booking.refresh_from_db()
        self.assertEqual(ticket.status, QueueTicket.SERVING)
        self.assertEqual(ticket.assigned_counter_id, self.counter.id)
        self.assertEqual(booking.status, Booking.CONFIRMED)

        completed = self.client.post(
            reverse("api_complete_current_ticket", args=[self.counter.id])
        )
        self.assertEqual(completed.status_code, status.HTTP_200_OK)
        ticket.refresh_from_db()
        booking.refresh_from_db()
        self.assertEqual(ticket.status, QueueTicket.COMPLETED)
        self.assertIsNone(ticket.assigned_counter_id)
        self.assertEqual(booking.status, Booking.COMPLETED)
        self.assertTrue(
            QueueEvent.objects.filter(booking=booking, event_type=QueueEvent.CALLED).exists()
        )
        self.assertTrue(
            QueueEvent.objects.filter(
                booking=booking, event_type=QueueEvent.COMPLETED
            ).exists()
        )

    def test_unassigned_counter_staff_cannot_operate_another_staff_members_counter(self):
        self._booking_ticket()
        self.client.force_authenticate(self.other_staff)

        response = self.client.post(
            reverse("api_call_next_ticket", args=[self.counter.id])
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_report_remains_branch_scoped_and_admin_global(self):
        self.client.force_authenticate(self.other_manager)
        denied = self.client.get(
            reverse("api_branch_operational_report", args=[self.branch.id])
        )
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(self.admin)
        allowed = self.client.get(
            reverse("api_branch_operational_report", args=[self.branch.id])
        )
        self.assertEqual(allowed.status_code, status.HTTP_200_OK)

    def test_locked_eta_contract_is_people_ahead_times_service_average(self):
        first_booking, _ = self._booking_ticket(queue_number="A001")
        first_booking.checked_in_at = timezone.now() - timedelta(minutes=2)
        first_booking.save(update_fields=["checked_in_at"])

        second_booking, second_ticket = self._booking_ticket(
            user=self.other_customer,
            queue_number="A002",
        )
        second_booking.checked_in_at = timezone.now()
        second_booking.save(update_fields=["checked_in_at"])

        prediction = get_ticket_prediction(second_ticket)
        self.assertEqual(prediction["people_ahead"], 1)
        self.assertEqual(prediction["estimated_wait_time"], 10)

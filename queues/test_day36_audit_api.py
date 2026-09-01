from datetime import date, time

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Profile
from bookings.models import Booking
from branches.models import Branch
from services.models import Service

from .events import record_queue_event
from .models import QueueEvent, QueueTicket


class Day36AuditAPITests(APITestCase):
    """Verify approved customer/manager/System Admin audit-read boundaries."""

    def setUp(self):
        self.branch = Branch.objects.create(
            branch_code="PTA01",
            name="Pretoria Branch",
            address="1 Main Street",
            city="Pretoria",
            opening_time=time(8, 0),
            closing_time=time(17, 0),
            is_active=True,
        )
        self.other_branch = Branch.objects.create(
            branch_code="JHB01",
            name="Johannesburg Branch",
            address="2 Main Street",
            city="Johannesburg",
            opening_time=time(8, 0),
            closing_time=time(17, 0),
            is_active=True,
        )
        self.service = Service.objects.create(
            service_code="ID01",
            name="ID Application",
            description="ID service",
            average_service_time=10,
            is_active=True,
        )

        self.customer = self._user("customer", Profile.CUSTOMER)
        self.other_customer = self._user("other_customer", Profile.CUSTOMER)
        self.manager = self._user(
            "manager", Profile.BRANCH_MANAGER, branch=self.branch
        )
        self.other_manager = self._user(
            "other_manager", Profile.BRANCH_MANAGER, branch=self.other_branch
        )
        self.receptionist = self._user(
            "reception", Profile.RECEPTIONIST, branch=self.branch
        )
        self.counter_staff = self._user(
            "counterstaff", Profile.COUNTER_STAFF, branch=self.branch
        )
        self.admin = self._user("admin", Profile.SYSTEM_ADMIN)

        self.booking = Booking.objects.create(
            user=self.customer,
            branch=self.branch,
            service=self.service,
            booking_date=date(2026, 9, 1),
            booking_time=time(9, 0),
            status=Booking.PENDING,
            source=Booking.ONLINE,
        )
        self.ticket = QueueTicket.objects.create(
            booking=self.booking,
            queue_number="A001",
            queue_type=QueueTicket.GENERAL,
            status=QueueTicket.SCHEDULED,
        )
        record_queue_event(
            QueueEvent.TICKET_SCHEDULED,
            ticket=self.ticket,
            booking=self.booking,
            actor=self.customer,
            to_ticket_status=QueueTicket.SCHEDULED,
            to_booking_status=Booking.PENDING,
        )

        self.other_booking = Booking.objects.create(
            user=self.other_customer,
            branch=self.other_branch,
            service=self.service,
            booking_date=date(2026, 9, 1),
            booking_time=time(10, 0),
            status=Booking.PENDING,
            source=Booking.ONLINE,
        )
        self.other_ticket = QueueTicket.objects.create(
            booking=self.other_booking,
            queue_number="A001",
            queue_type=QueueTicket.GENERAL,
            status=QueueTicket.SCHEDULED,
        )
        record_queue_event(
            QueueEvent.TICKET_SCHEDULED,
            ticket=self.other_ticket,
            booking=self.other_booking,
            actor=self.other_customer,
            to_ticket_status=QueueTicket.SCHEDULED,
            to_booking_status=Booking.PENDING,
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

    def test_customer_can_read_only_own_booking_timeline(self):
        self.client.force_authenticate(self.customer)

        own_url = reverse("api_customer_booking_timeline", args=[self.booking.id])
        own_response = self.client.get(own_url)
        self.assertEqual(own_response.status_code, status.HTTP_200_OK)
        self.assertEqual(own_response.data["booking_id"], self.booking.id)
        self.assertEqual(len(own_response.data["events"]), 1)
        self.assertEqual(
            own_response.data["events"][0]["event_type"],
            QueueEvent.TICKET_SCHEDULED,
        )
        # Customer response deliberately excludes staff audit identity/metadata.
        self.assertNotIn("actor_username", own_response.data["events"][0])
        self.assertNotIn("metadata", own_response.data["events"][0])

        other_url = reverse(
            "api_customer_booking_timeline", args=[self.other_booking.id]
        )
        other_response = self.client.get(other_url)
        self.assertEqual(other_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_branch_manager_reads_only_own_branch_audit(self):
        self.client.force_authenticate(self.manager)

        own_url = reverse("api_branch_queue_event_audit", args=[self.branch.id])
        own_response = self.client.get(own_url)
        self.assertEqual(own_response.status_code, status.HTTP_200_OK)
        self.assertEqual(own_response.data["branch_id"], self.branch.id)
        self.assertEqual(len(own_response.data["events"]), 1)
        self.assertEqual(
            own_response.data["events"][0]["actor_username"], "customer"
        )

        other_url = reverse(
            "api_branch_queue_event_audit", args=[self.other_branch.id]
        )
        other_response = self.client.get(other_url)
        self.assertEqual(other_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_system_admin_can_read_any_branch_audit(self):
        self.client.force_authenticate(self.admin)

        for branch in [self.branch, self.other_branch]:
            response = self.client.get(
                reverse("api_branch_queue_event_audit", args=[branch.id])
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data["branch_id"], branch.id)
            self.assertEqual(len(response.data["events"]), 1)

    def test_receptionist_and_counter_staff_cannot_read_full_audit(self):
        url = reverse("api_branch_queue_event_audit", args=[self.branch.id])

        for user in [self.receptionist, self.counter_staff]:
            self.client.force_authenticate(user)
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_other_branch_manager_does_not_gain_access_via_event_ids(self):
        """Branch audit is selected from the authorised Branch, never arbitrary events."""
        self.client.force_authenticate(self.other_manager)
        response = self.client.get(
            reverse("api_branch_queue_event_audit", args=[self.branch.id])
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

from datetime import date, time

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounts.models import Profile
from bookings.models import Booking, GuestCustomer
from branches.models import Branch
from counters.models import Counter
from queues.models import QueueTicket
from services.models import Service


class ManagerDashboardAPITests(APITestCase):
    """Day 34 coverage for the branch manager dashboard read model."""

    def setUp(self):
        self.report_date = date(2026, 8, 31)
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

        self.manager = User.objects.create_user(username="manager", password="pw")
        Profile.objects.create(
            user=self.manager,
            date_of_birth=date(1985, 1, 1),
            gender=Profile.OTHER,
            role=Profile.BRANCH_MANAGER,
            branch=self.branch,
        )
        self.other_manager = User.objects.create_user(
            username="othermanager", password="pw"
        )
        Profile.objects.create(
            user=self.other_manager,
            date_of_birth=date(1986, 1, 1),
            gender=Profile.OTHER,
            role=Profile.BRANCH_MANAGER,
            branch=self.other_branch,
        )
        self.admin = User.objects.create_user(username="admin", password="pw")
        Profile.objects.create(
            user=self.admin,
            date_of_birth=date(1980, 1, 1),
            gender=Profile.OTHER,
            role=Profile.SYSTEM_ADMIN,
        )
        self.customer = User.objects.create_user(username="customer", password="pw")
        Profile.objects.create(
            user=self.customer,
            date_of_birth=date(1995, 1, 1),
            gender=Profile.OTHER,
            role=Profile.CUSTOMER,
        )
        self.staff = User.objects.create_user(username="staff", password="pw")
        Profile.objects.create(
            user=self.staff,
            date_of_birth=date(1990, 1, 1),
            gender=Profile.OTHER,
            role=Profile.COUNTER_STAFF,
            branch=self.branch,
        )

        self.service = Service.objects.create(
            service_code="ID01",
            name="ID Application",
            description="Identity document service",
            average_service_time=10,
        )
        self.second_service = Service.objects.create(
            service_code="PASS01",
            name="Passport Application",
            description="Passport service",
            average_service_time=15,
        )

        # Scheduled online booking: has not entered the live queue yet.
        scheduled_booking = Booking.objects.create(
            user=self.customer,
            branch=self.branch,
            service=self.service,
            booking_date=self.report_date,
            booking_time=time(10, 0),
            status=Booking.PENDING,
            source=Booking.ONLINE,
        )
        QueueTicket.objects.create(
            booking=scheduled_booking,
            queue_number="A001",
            queue_type=QueueTicket.GENERAL,
            status=QueueTicket.SCHEDULED,
        )

        # Checked-in guest walk-in currently waiting in the Priority queue.
        self.guest = GuestCustomer.objects.create(
            full_name="Guest One",
            phone_number="",
            date_of_birth=date(1960, 1, 1),
            gender=Profile.OTHER,
        )
        waiting_booking = Booking.objects.create(
            guest_customer=self.guest,
            branch=self.branch,
            service=self.second_service,
            booking_date=self.report_date,
            booking_time=time(9, 0),
            status=Booking.PENDING,
            source=Booking.WALK_IN,
            checked_in_at="2026-08-31T07:00:00Z",
        )
        QueueTicket.objects.create(
            booking=waiting_booking,
            queue_number="P001",
            queue_type=QueueTicket.PRIORITY,
            status=QueueTicket.WAITING,
        )

        # Online customer currently being served at an assigned OPEN counter.
        serving_booking = Booking.objects.create(
            user=self.customer,
            branch=self.branch,
            service=self.service,
            booking_date=self.report_date,
            booking_time=time(9, 30),
            status=Booking.CONFIRMED,
            source=Booking.ONLINE,
            checked_in_at="2026-08-31T07:15:00Z",
        )
        self.open_counter = Counter.objects.create(
            branch=self.branch,
            counter_number="1",
            queue_type=QueueTicket.GENERAL,
            assigned_staff=self.staff,
            status=Counter.OPEN,
        )
        QueueTicket.objects.create(
            booking=serving_booking,
            queue_number="A002",
            queue_type=QueueTicket.GENERAL,
            status=QueueTicket.SERVING,
            assigned_counter=self.open_counter,
        )

        Counter.objects.create(
            branch=self.branch,
            counter_number="2",
            queue_type=QueueTicket.PRIORITY,
            status=Counter.CLOSED,
        )

        self.client = APIClient()

    def _url(self, branch=None):
        branch = branch or self.branch
        return reverse(
            "api_branch_manager_dashboard",
            kwargs={"branch_id": branch.id},
        )

    def test_manager_dashboard_returns_truthful_branch_aggregates(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.get(
            self._url(),
            {"date": self.report_date.isoformat()},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["branch"]["id"], self.branch.id)
        self.assertEqual(response.data["customers"]["total_customers"], 3)
        self.assertEqual(response.data["lifecycle_totals"]["scheduled"], 1)
        self.assertEqual(response.data["lifecycle_totals"]["waiting"], 1)
        self.assertEqual(response.data["lifecycle_totals"]["serving"], 1)
        self.assertEqual(response.data["booking_sources"]["online"], 2)
        self.assertEqual(response.data["booking_sources"]["walk_in"], 1)
        self.assertEqual(response.data["check_in"]["checked_in"], 2)
        self.assertEqual(response.data["check_in"]["not_checked_in"], 1)

    def test_dashboard_contains_service_and_live_counter_state(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.get(
            self._url(),
            {"date": self.report_date.isoformat()},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        service_counts = {
            item["service_code"]: item["customers"]
            for item in response.data["services"]
        }
        self.assertEqual(service_counts["ID01"], 2)
        self.assertEqual(service_counts["PASS01"], 1)

        counter_summary = response.data["counters"]["summary"]
        self.assertEqual(counter_summary["total"], 2)
        self.assertEqual(counter_summary["open"], 1)
        self.assertEqual(counter_summary["closed"], 1)
        self.assertEqual(counter_summary["staffed"], 1)
        self.assertEqual(counter_summary["unstaffed"], 1)
        self.assertEqual(counter_summary["busy"], 1)
        self.assertEqual(counter_summary["free"], 0)

        first_counter = response.data["counters"]["counters"][0]
        self.assertEqual(first_counter["assigned_staff_username"], "staff")
        self.assertTrue(first_counter["is_busy"])
        self.assertEqual(
            first_counter["current_customer"]["queue_number"],
            "A002",
        )

    def test_branch_manager_cannot_read_another_branch_dashboard(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.get(
            self._url(branch=self.other_branch),
            {"date": self.report_date.isoformat()},
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_system_admin_can_read_any_branch_dashboard(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(
            self._url(branch=self.other_branch),
            {"date": self.report_date.isoformat()},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_counter_staff_cannot_read_manager_dashboard(self):
        self.client.force_authenticate(user=self.staff)
        response = self.client.get(
            self._url(),
            {"date": self.report_date.isoformat()},
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_invalid_date_is_rejected(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.get(self._url(), {"date": "31-08-2026"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["detail"],
            "date must use YYYY-MM-DD format.",
        )

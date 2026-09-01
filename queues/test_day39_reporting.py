from datetime import date, datetime, time, timezone as dt_timezone

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


class Day39OperationalReportingTests(APITestCase):
    def setUp(self):
        self.branch = self._branch("PTA01", "Pretoria Branch")
        self.other_branch = self._branch("JHB01", "Johannesburg Branch")
        self.service = Service.objects.create(
            service_code="ID01",
            name="ID Application",
            description="ID service",
            average_service_time=10,
            is_active=True,
        )

        self.customer = self._user("customer", Profile.CUSTOMER)
        self.manager = self._user("manager", Profile.BRANCH_MANAGER, self.branch)
        self.other_manager = self._user(
            "other_manager", Profile.BRANCH_MANAGER, self.other_branch
        )
        self.receptionist = self._user(
            "reception", Profile.RECEPTIONIST, self.branch
        )
        self.admin = self._user("admin", Profile.SYSTEM_ADMIN)

        self._create_completed_journey()
        self._create_no_show_journey()
        self._create_cancelled_journey()
        self._create_other_branch_journey()
        self._create_outside_period_event()

    def _branch(self, code, name):
        return Branch.objects.create(
            branch_code=code,
            name=name,
            address="1 Main Street",
            city="Pretoria",
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

    def _booking_ticket(self, branch, queue_number, queue_type):
        booking = Booking.objects.create(
            user=self.customer,
            branch=branch,
            service=self.service,
            booking_date=date(2026, 9, 1),
            booking_time=time(9, 0),
            status=Booking.PENDING,
            source=Booking.ONLINE,
        )
        ticket = QueueTicket.objects.create(
            booking=booking,
            queue_number=queue_number,
            queue_type=queue_type,
            status=QueueTicket.WAITING,
        )
        return booking, ticket

    def _at(self, hour, minute=0, day=1):
        return datetime(2026, 9, day, hour, minute, tzinfo=dt_timezone.utc)

    def _event(self, event_type, booking, ticket, occurred_at):
        return record_queue_event(
            event_type,
            booking=booking,
            ticket=ticket,
            actor=self.customer,
            occurred_at=occurred_at,
        )

    def _create_completed_journey(self):
        booking, ticket = self._booking_ticket(
            self.branch, "A001", QueueTicket.GENERAL
        )
        self._event(QueueEvent.CHECKED_IN, booking, ticket, self._at(9, 0))
        self._event(QueueEvent.CALLED, booking, ticket, self._at(9, 15))
        self._event(QueueEvent.COMPLETED, booking, ticket, self._at(9, 25))

    def _create_no_show_journey(self):
        booking, ticket = self._booking_ticket(
            self.branch, "P001", QueueTicket.PRIORITY
        )
        self._event(QueueEvent.CHECKED_IN, booking, ticket, self._at(10, 0))
        self._event(QueueEvent.CALLED, booking, ticket, self._at(10, 5))
        self._event(QueueEvent.NO_SHOW, booking, ticket, self._at(10, 6))

    def _create_cancelled_journey(self):
        booking, ticket = self._booking_ticket(
            self.branch, "A002", QueueTicket.GENERAL
        )
        self._event(QueueEvent.CHECKED_IN, booking, ticket, self._at(11, 0))
        self._event(QueueEvent.CANCELLED, booking, ticket, self._at(11, 10))

    def _create_other_branch_journey(self):
        booking, ticket = self._booking_ticket(
            self.other_branch, "A001", QueueTicket.GENERAL
        )
        self._event(QueueEvent.CHECKED_IN, booking, ticket, self._at(12, 0))
        self._event(QueueEvent.COMPLETED, booking, ticket, self._at(12, 10))

    def _create_outside_period_event(self):
        booking, ticket = self._booking_ticket(
            self.branch, "A099", QueueTicket.GENERAL
        )
        self._event(QueueEvent.CHECKED_IN, booking, ticket, self._at(9, 0, day=3))

    def _url(self, branch=None, query=""):
        url = reverse(
            "api_branch_operational_report",
            args=[(branch or self.branch).id],
        )
        return f"{url}?{query}" if query else url

    def test_manager_report_uses_queue_event_history_and_calculates_actual_timings(self):
        self.client.force_authenticate(self.manager)
        response = self.client.get(
            self._url(query="start_date=2026-09-01&end_date=2026-09-01")
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["branch_id"], self.branch.id)
        self.assertEqual(response.data["summary"]["checked_in"], 3)
        self.assertEqual(response.data["summary"]["called"], 2)
        self.assertEqual(response.data["summary"]["completed"], 1)
        self.assertEqual(response.data["summary"]["no_show"], 1)
        self.assertEqual(response.data["summary"]["cancelled"], 1)
        self.assertEqual(response.data["timing"]["average_actual_wait_minutes"], 10.0)
        self.assertEqual(response.data["timing"]["average_service_minutes"], 10.0)
        self.assertEqual(response.data["timing"]["measured_waits"], 2)
        self.assertEqual(response.data["timing"]["measured_services"], 1)
        self.assertEqual(response.data["outcomes"]["completion_rate_percent"], 50.0)
        self.assertEqual(response.data["outcomes"]["no_show_rate_percent"], 50.0)
        self.assertEqual(
            response.data["queue_type_check_ins"],
            {QueueTicket.GENERAL: 2, QueueTicket.PRIORITY: 1},
        )
        self.assertEqual(response.data["source_check_ins"], {QueueEvent.CUSTOMER: 3})
        self.assertEqual(len(response.data["daily_activity"]), 1)
        self.assertEqual(response.data["services"][0]["completed"], 1)

    def test_report_is_branch_scoped_and_role_protected(self):
        self.client.force_authenticate(self.other_manager)
        denied = self.client.get(
            self._url(query="start_date=2026-09-01&end_date=2026-09-01")
        )
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(self.receptionist)
        denied = self.client.get(
            self._url(query="start_date=2026-09-01&end_date=2026-09-01")
        )
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(self.admin)
        allowed = self.client.get(
            self._url(query="start_date=2026-09-01&end_date=2026-09-01")
        )
        self.assertEqual(allowed.status_code, status.HTTP_200_OK)

    def test_report_period_validation_rejects_invalid_and_oversized_ranges(self):
        self.client.force_authenticate(self.manager)

        invalid = self.client.get(
            self._url(query="start_date=bad-date&end_date=2026-09-01")
        )
        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)

        reversed_period = self.client.get(
            self._url(query="start_date=2026-09-02&end_date=2026-09-01")
        )
        self.assertEqual(reversed_period.status_code, status.HTTP_400_BAD_REQUEST)

        oversized = self.client.get(
            self._url(query="start_date=2025-01-01&end_date=2026-09-01")
        )
        self.assertEqual(oversized.status_code, status.HTTP_400_BAD_REQUEST)

    def test_branch_time_index_supports_report_range_query_on_sqlite(self):
        queryset = QueueEvent.objects.filter(
            branch=self.branch,
            occurred_at__gte=self._at(0, 0),
            occurred_at__lt=self._at(0, 0, day=2),
        )
        plan = queryset.explain()
        self.assertIn("queue_evt_branch_time", plan)

from datetime import date, time, timedelta

from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Profile
from bookings.models import Booking
from branches.models import Branch
from queues.events import record_queue_event
from queues.models import QueueEvent, QueuePause, QueueTicket
from rescheduling.models import RescheduleRecommendation
from services.models import BranchService, Service


class Day49HistoryRecoveryTests(APITestCase):
    """Integration coverage for historical reporting, disruption restore and customer recovery."""

    def setUp(self):
        self.branch = self._branch("PTA49", "Pretoria Day 49")
        self.other_branch = self._branch("JHB49", "Johannesburg Day 49")
        self.service = Service.objects.create(
            service_code="D49",
            name="Day 49 Service",
            description="History and recovery test service",
            average_service_time=10,
            is_active=True,
        )
        BranchService.objects.create(
            branch=self.branch,
            service=self.service,
            max_bookings_per_slot=2,
            is_active=True,
        )

        self.manager = self._user("day49_manager", Profile.BRANCH_MANAGER, self.branch)
        self.other_manager = self._user(
            "day49_other_manager", Profile.BRANCH_MANAGER, self.other_branch
        )
        self.admin = self._user("day49_admin", Profile.SYSTEM_ADMIN)
        self.customer = self._user("day49_customer", Profile.CUSTOMER)
        self.receptionist = self._user(
            "day49_reception", Profile.RECEPTIONIST, self.branch
        )

        self.booking = Booking.objects.create(
            user=self.customer,
            branch=self.branch,
            service=self.service,
            booking_date=timezone.localdate(),
            booking_time=time(9, 0),
            status=Booking.CONFIRMED,
            source=Booking.ONLINE,
            checked_in_at=timezone.now() - timedelta(minutes=30),
        )
        self.ticket = QueueTicket.objects.create(
            booking=self.booking,
            queue_number="A049",
            queue_type=QueueTicket.GENERAL,
            status=QueueTicket.WAITING,
        )
        record_queue_event(
            QueueEvent.CHECKED_IN,
            booking=self.booking,
            ticket=self.ticket,
            actor=self.customer,
            occurred_at=timezone.now() - timedelta(minutes=30),
        )

    def _branch(self, code, name):
        return Branch.objects.create(
            branch_code=code,
            name=name,
            address="49 Main Street",
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

    def test_day49_frontend_routes_and_assets_are_present(self):
        history = self.client.get(reverse("frontend_history_reporting_workspace"))
        recovery = self.client.get(reverse("frontend_customer_recovery_workspace"))

        self.assertEqual(history.status_code, status.HTTP_200_OK)
        self.assertContains(history, "data-history-workspace")
        self.assertContains(history, "data-audit-body")
        self.assertContains(history, "data-pause-form")
        self.assertEqual(recovery.status_code, status.HTTP_200_OK)
        self.assertContains(recovery, "data-customer-recovery")
        self.assertContains(recovery, "data-recovery-list")

        self.assertIsNotNone(finders.find("css/day49-workflows.css"))
        self.assertIsNotNone(finders.find("js/pages/history-reporting-workspace.js"))
        self.assertIsNotNone(finders.find("js/pages/customer-recovery-workspace.js"))

    def test_branch_pause_list_restores_state_and_preserves_scope(self):
        active = QueuePause.objects.create(
            branch=self.branch,
            service=self.service,
            booking_date=timezone.localdate(),
            reason="Network outage",
            is_active=True,
        )
        QueuePause.objects.create(
            branch=self.branch,
            service=self.service,
            booking_date=timezone.localdate() - timedelta(days=1),
            reason="Earlier outage",
            ended_at=timezone.now(),
            is_active=False,
        )

        url = reverse("api_branch_queue_pause_create", args=[self.branch.id])
        self.client.force_authenticate(self.manager)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["branch_id"], self.branch.id)
        self.assertEqual(len(response.data["pauses"]), 2)
        self.assertEqual(response.data["pauses"][0]["pause_impact"]["id"], active.id)

        self.client.force_authenticate(self.other_manager)
        denied = self.client.get(url)
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(self.admin)
        global_access = self.client.get(url)
        self.assertEqual(global_access.status_code, status.HTTP_200_OK)

    def test_management_history_apis_match_day49_role_scope(self):
        report_url = reverse("api_branch_operational_report", args=[self.branch.id])
        audit_url = reverse("api_branch_queue_event_audit", args=[self.branch.id])

        self.client.force_authenticate(self.manager)
        report = self.client.get(report_url)
        audit = self.client.get(audit_url)
        self.assertEqual(report.status_code, status.HTTP_200_OK)
        self.assertEqual(audit.status_code, status.HTTP_200_OK)
        self.assertEqual(report.data["branch_id"], self.branch.id)
        self.assertEqual(audit.data["branch_id"], self.branch.id)
        self.assertGreaterEqual(report.data["summary"]["checked_in"], 1)
        self.assertTrue(any(item["event_type"] == QueueEvent.CHECKED_IN for item in audit.data["events"]))

        self.client.force_authenticate(self.receptionist)
        self.assertEqual(self.client.get(report_url).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.get(audit_url).status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get(report_url).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(audit_url).status_code, status.HTTP_200_OK)

    def test_manager_disruption_to_customer_recovery_end_to_end(self):
        pause_url = reverse("api_branch_queue_pause_create", args=[self.branch.id])
        self.client.force_authenticate(self.manager)
        pause_response = self.client.post(
            pause_url,
            {
                "service_id": self.service.id,
                "booking_date": timezone.localdate().isoformat(),
                "reason": "Connectivity failure",
            },
            format="json",
        )
        self.assertEqual(pause_response.status_code, status.HTTP_201_CREATED)
        pause_id = pause_response.data["pause_impact"]["id"]

        # Simulate enough elapsed outage time to consume at least one service
        # opportunity. The backend disruption logic, not the UI, determines risk.
        QueuePause.objects.filter(pk=pause_id).update(
            started_at=timezone.now() - timedelta(minutes=20)
        )

        restored = self.client.get(pause_url)
        self.assertEqual(restored.status_code, status.HTTP_200_OK)
        self.assertEqual(restored.data["pauses"][0]["pause_impact"]["id"], pause_id)

        resume = self.client.post(
            reverse("api_queue_pause_resume", args=[pause_id]),
            {},
            format="json",
        )
        self.assertEqual(resume.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(resume.data["impact_processing"]["affected_processed"], 1)
        self.assertGreaterEqual(
            resume.data["impact_processing"]["reschedule_risk_processed"], 1
        )
        self.assertGreaterEqual(resume.data["rescheduling"]["recommendations_created"], 1)

        self.client.force_authenticate(self.customer)
        recommendations = self.client.get(reverse("api_my_reschedule_recommendations"))
        self.assertEqual(recommendations.status_code, status.HTTP_200_OK)
        self.assertEqual(len(recommendations.data), 1)
        self.assertEqual(recommendations.data[0]["booking_id"], self.booking.id)
        self.assertEqual(recommendations.data[0]["status"], RescheduleRecommendation.PENDING)
        self.assertGreaterEqual(len(recommendations.data[0]["options"]), 1)

        option_id = recommendations.data[0]["options"][0]["id"]
        applied = self.client.post(
            reverse("api_customer_reschedule_option_select", args=[option_id]),
            {},
            format="json",
        )
        self.assertEqual(applied.status_code, status.HTTP_200_OK)
        self.assertEqual(applied.data["status"], RescheduleRecommendation.APPLIED)

        self.booking.refresh_from_db()
        self.ticket.refresh_from_db()
        self.assertGreater(self.booking.booking_date, timezone.localdate())
        self.assertEqual(self.booking.status, Booking.PENDING)
        self.assertIsNone(self.booking.checked_in_at)
        self.assertEqual(self.ticket.status, QueueTicket.SCHEDULED)
        self.assertEqual(self.ticket.queue_type, QueueTicket.PRIORITY)
        self.assertTrue(self.ticket.queue_number.startswith("P"))

        audit = self.client.get(
            reverse("api_customer_booking_timeline", args=[self.booking.id])
        )
        self.assertEqual(audit.status_code, status.HTTP_200_OK)
        self.assertTrue(
            any(
                item["event_type"] == QueueEvent.DISRUPTION_RESCHEDULED
                for item in audit.data["events"]
            )
        )

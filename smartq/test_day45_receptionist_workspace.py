from datetime import date, datetime, time
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Profile
from bookings.models import Booking
from branches.models import Branch
from queues.models import QueueTicket
from services.models import BranchService, Service


class Day45ReceptionistWorkspaceTests(APITestCase):
    def setUp(self):
        self.branch = Branch.objects.create(
            branch_code="D45A",
            name="Day 45 Reception Branch",
            address="45 Queue Street",
            city="Pretoria",
            opening_time=time(8, 0),
            closing_time=time(17, 0),
            is_active=True,
        )
        self.other_branch = Branch.objects.create(
            branch_code="D45B",
            name="Day 45 Other Branch",
            address="46 Queue Street",
            city="Johannesburg",
            opening_time=time(8, 0),
            closing_time=time(17, 0),
            is_active=True,
        )
        self.service = Service.objects.create(
            service_code="D45ID",
            name="Identity Service",
            description="Day 45 identity service",
            average_service_time=15,
            is_active=True,
        )
        BranchService.objects.create(
            branch=self.branch,
            service=self.service,
            max_bookings_per_slot=2,
        )
        self.receptionist = User.objects.create_user(username="day45reception", password="pw")
        Profile.objects.create(
            user=self.receptionist,
            date_of_birth=date(1990, 1, 1),
            gender=Profile.OTHER,
            role=Profile.RECEPTIONIST,
            branch=self.branch,
        )
        self.customer = User.objects.create_user(
            username="day45customer",
            first_name="Daya",
            last_name="Customer",
            email="day45@example.com",
            password="pw",
        )
        Profile.objects.create(
            user=self.customer,
            date_of_birth=date(1996, 6, 1),
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
            queue_number="A045",
            queue_type=QueueTicket.GENERAL,
            status=QueueTicket.SCHEDULED,
        )
        self.client.force_authenticate(user=self.receptionist)

    def _aware_today(self, hour, minute=0):
        value = datetime.combine(timezone.localdate(), time(hour, minute))
        return timezone.make_aware(value, timezone.get_current_timezone())

    def test_reception_workspace_renders_day45_operating_contract(self):
        response = self.client.get(reverse("frontend_reception_workspace"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-reception-dashboard')
        self.assertContains(response, 'data-reception-search-form')
        self.assertContains(response, 'data-walk-in-form')
        self.assertContains(response, 'data-queue-body')
        self.assertContains(response, 'data-expected-role="receptionist"')
        self.assertContains(response, "Reception captures facts. The backend decides priority.")
        self.assertContains(response, "/static/js/pages/reception-dashboard.js")
        self.assertContains(response, "/static/css/reception-dashboard.css")

    def test_day45_frontend_assets_use_existing_reception_contract(self):
        script_path = Path(finders.find("js/pages/reception-dashboard.js"))
        stylesheet_path = Path(finders.find("css/reception-dashboard.css"))
        script = script_path.read_text(encoding="utf-8")

        self.assertTrue(stylesheet_path.exists())
        for endpoint_fragment in [
            "/api/v1/bookings/reception/search/",
            "/staff-check-in/",
            "/api/v1/bookings/reception/walk-ins/",
            "/api/v1/queues/branches/",
            "/api/v1/services/branches/",
        ]:
            with self.subTest(endpoint=endpoint_fragment):
                self.assertIn(endpoint_fragment, script)
        self.assertNotIn("queue_type:", script)
        self.assertNotIn("queue_number:", script)

    def test_branch_scoped_search_drives_assisted_check_in_and_waiting_queue(self):
        search = self.client.get(reverse("api_reception_booking_search"), {"q": "Daya"})
        self.assertEqual(search.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in search.data], [self.booking.id])

        with patch("queues.services.timezone.now", return_value=self._aware_today(10, 0)):
            checked_in = self.client.post(
                reverse("api_staff_booking_check_in", kwargs={"pk": self.booking.id})
            )

        self.assertEqual(checked_in.status_code, status.HTTP_200_OK)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, QueueTicket.WAITING)

        waiting = self.client.get(
            reverse("api_branch_waiting_queue", kwargs={"branch_id": self.branch.id})
        )
        self.assertEqual(waiting.status_code, status.HTTP_200_OK)
        self.assertEqual([item["booking_id"] for item in waiting.data], [self.booking.id])
        self.assertEqual(waiting.data[0]["customer_name"], "Daya Customer")

    def test_guest_walk_in_joins_waiting_with_backend_allocated_priority(self):
        response = self.client.post(
            reverse("api_reception_guest_walk_in"),
            {
                "full_name": "Priority Guest",
                "phone_number": "0712345678",
                "date_of_birth": "1950-01-01",
                "gender": Profile.OTHER,
                "disability_status": False,
                "is_pregnant": False,
                "service": self.service.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        booking = Booking.objects.get(pk=response.data["id"])
        ticket = booking.queueticket
        self.assertEqual(booking.branch, self.branch)
        self.assertEqual(booking.source, Booking.WALK_IN)
        self.assertIsNotNone(booking.checked_in_at)
        self.assertEqual(ticket.status, QueueTicket.WAITING)
        self.assertEqual(ticket.queue_type, QueueTicket.PRIORITY)
        self.assertTrue(ticket.queue_number.startswith("P"))

    def test_receptionist_cannot_cross_branch_waiting_queue_boundary(self):
        response = self.client.get(
            reverse("api_branch_waiting_queue", kwargs={"branch_id": self.other_branch.id})
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_customer_cannot_use_reception_workflows(self):
        self.client.force_authenticate(user=self.customer)
        search = self.client.get(reverse("api_reception_booking_search"), {"q": "Daya"})
        walk_in = self.client.post(
            reverse("api_reception_guest_walk_in"),
            {
                "full_name": "Blocked Guest",
                "date_of_birth": "1990-01-01",
                "gender": Profile.OTHER,
                "service": self.service.id,
            },
            format="json",
        )

        self.assertEqual(search.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(walk_in.status_code, status.HTTP_403_FORBIDDEN)

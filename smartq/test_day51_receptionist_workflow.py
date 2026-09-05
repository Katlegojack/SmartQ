from datetime import date, time, timedelta
from pathlib import Path

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


class Day51ReceptionistWorkflowTests(APITestCase):
    def setUp(self):
        self.branch = Branch.objects.create(
            branch_code="D51",
            name="Day 51 Branch",
            address="51 Main Street",
            city="Kimberley",
            opening_time=time(8, 0),
            closing_time=time(17, 0),
            is_active=True,
        )
        self.other_branch = Branch.objects.create(
            branch_code="D51B",
            name="Other Branch",
            address="52 Main Street",
            city="Kimberley",
            opening_time=time(8, 0),
            closing_time=time(17, 0),
            is_active=True,
        )
        self.service = Service.objects.create(
            service_code="D51S",
            name="Identity Service",
            description="Day 51 reception service",
            average_service_time=15,
            is_active=True,
        )
        BranchService.objects.create(
            branch=self.branch,
            service=self.service,
            max_bookings_per_slot=6,
            is_active=True,
        )
        BranchService.objects.create(
            branch=self.other_branch,
            service=self.service,
            max_bookings_per_slot=6,
            is_active=True,
        )

        self.receptionist = User.objects.create_user(
            username="day51reception",
            password="SafePassword123!",
            first_name="Reneilwe",
        )
        Profile.objects.create(
            user=self.receptionist,
            date_of_birth=date(1992, 3, 4),
            gender=Profile.OTHER,
            role=Profile.RECEPTIONIST,
            branch=self.branch,
        )

        self.customer = User.objects.create_user(
            username="day51customer",
            password="SafePassword123!",
            first_name="Thato",
            last_name="Mokoena",
        )
        Profile.objects.create(
            user=self.customer,
            date_of_birth=date(1996, 6, 12),
            gender=Profile.OTHER,
            role=Profile.CUSTOMER,
        )

        self.today_booking = Booking.objects.create(
            user=self.customer,
            branch=self.branch,
            service=self.service,
            booking_date=timezone.localdate(),
            booking_time=time(15, 0),
            status=Booking.PENDING,
            source=Booking.ONLINE,
        )
        QueueTicket.objects.create(
            booking=self.today_booking,
            queue_number="A001",
            queue_type=QueueTicket.GENERAL,
            status=QueueTicket.SCHEDULED,
        )

    def authenticate_receptionist(self):
        self.client.force_authenticate(self.receptionist)

    def test_reception_page_is_job_first_and_removes_engineering_copy(self):
        response = self.client.get(reverse("frontend_reception_workspace"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for required in ["Today's customers", "Live queue", "Add walk-in"]:
            self.assertContains(response, required)
        for banned in [
            "Day 45 operational workspace",
            "backend",
            "Reception never chooses General or Priority",
            "Branch scoped",
            "Session active",
            "Focus search",
        ]:
            self.assertNotContains(response, banned)
        self.assertContains(response, "data-today-table")
        self.assertContains(response, "data-walkin-form")

    def test_today_endpoint_returns_only_non_final_customers_in_assigned_branch(self):
        other_customer = User.objects.create_user(username="other51", password="pw")
        Profile.objects.create(
            user=other_customer,
            date_of_birth=date(1995, 1, 1),
            gender=Profile.OTHER,
            role=Profile.CUSTOMER,
        )
        Booking.objects.create(
            user=other_customer,
            branch=self.other_branch,
            service=self.service,
            booking_date=timezone.localdate(),
            booking_time=time(10, 0),
            status=Booking.PENDING,
        )
        Booking.objects.create(
            user=other_customer,
            branch=self.branch,
            service=self.service,
            booking_date=timezone.localdate(),
            booking_time=time(11, 0),
            status=Booking.COMPLETED,
        )
        Booking.objects.create(
            user=other_customer,
            branch=self.branch,
            service=self.service,
            booking_date=timezone.localdate() + timedelta(days=1),
            booking_time=time(11, 0),
            status=Booking.PENDING,
        )

        self.authenticate_receptionist()
        response = self.client.get(reverse("api_reception_today_bookings"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in response.data], [self.today_booking.id])
        self.assertEqual(response.data[0]["customer_name"], "Thato Mokoena")
        self.assertEqual(response.data[0]["queue_ticket"]["status"], QueueTicket.SCHEDULED)

    def test_customer_self_service_queue_entry_is_visible_to_reception(self):
        self.client.force_authenticate(self.customer)
        join_response = self.client.post(
            reverse("api_customer_walk_in"),
            {"branch": self.branch.id, "service": self.service.id},
            format="json",
        )
        self.assertEqual(join_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(join_response.data["queue_ticket"]["status"], QueueTicket.WAITING)

        self.authenticate_receptionist()
        today_response = self.client.get(reverse("api_reception_today_bookings"))
        waiting_response = self.client.get(
            reverse("api_branch_waiting_queue", args=[self.branch.id])
        )

        self.assertEqual(today_response.status_code, status.HTTP_200_OK)
        self.assertEqual(waiting_response.status_code, status.HTTP_200_OK)
        joined_id = join_response.data["id"]
        today_joined = next(item for item in today_response.data if item["id"] == joined_id)
        self.assertEqual(today_joined["queue_ticket"]["status"], QueueTicket.WAITING)
        self.assertTrue(
            any(item["booking_id"] == joined_id for item in waiting_response.data)
        )

    def test_customer_cannot_read_reception_today_workload(self):
        self.client.force_authenticate(self.customer)
        response = self.client.get(reverse("api_reception_today_bookings"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_browser_module_uses_today_contract_and_background_refresh(self):
        path = Path(finders.find("js/pages/reception-workspace.js"))
        source = path.read_text(encoding="utf-8")

        self.assertIn('/api/v1/bookings/reception/today/', source)
        self.assertIn("const AUTO_REFRESH_MS = 15000", source)
        self.assertIn("window.setInterval", source)
        self.assertIn("if (!searchMode) loadToday({ silent: true })", source)

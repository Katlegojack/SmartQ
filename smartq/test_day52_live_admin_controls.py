from datetime import datetime, time
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Profile
from branches.models import Branch
from services.availability import get_slot_availability
from services.models import BranchService, Service


class Day52LiveStateAndAdminControlTests(APITestCase):
    """Protect the live customer workflow and System Admin configuration controls."""

    def setUp(self):
        self.admin = User.objects.create_user(
            username="day52admin",
            password="SafePassword123!",
        )
        Profile.objects.create(
            user=self.admin,
            date_of_birth=timezone.localdate().replace(year=1990),
            gender=Profile.OTHER,
            role=Profile.SYSTEM_ADMIN,
        )

        self.customer = User.objects.create_user(
            username="day52customer",
            password="SafePassword123!",
            first_name="Live",
            last_name="Customer",
        )
        Profile.objects.create(
            user=self.customer,
            date_of_birth=timezone.localdate().replace(year=1995),
            gender=Profile.OTHER,
            role=Profile.CUSTOMER,
        )

        self.branch = Branch.objects.create(
            branch_code="D52A",
            name="Day 52 Branch",
            address="52 Main Street",
            city="Kimberley",
            opening_time=time(8, 0),
            closing_time=time(17, 0),
            is_active=True,
        )
        self.service = Service.objects.create(
            service_code="D52S",
            name="Day 52 Service",
            description="Live-state regression service",
            average_service_time=30,
            is_active=True,
        )
        BranchService.objects.create(
            branch=self.branch,
            service=self.service,
            max_bookings_per_slot=4,
            is_active=True,
        )

    def test_default_operating_timezone_is_south_african_local_time(self):
        self.assertEqual(settings.TIME_ZONE, "Africa/Johannesburg")

    def test_same_day_availability_excludes_times_that_have_already_passed(self):
        today = timezone.localdate()
        local_now = timezone.make_aware(
            datetime.combine(today, time(14, 0)),
            timezone.get_current_timezone(),
        )

        slots = get_slot_availability(
            self.branch,
            self.service,
            today,
            now=local_now,
        )
        times = [slot["time"] for slot in slots]

        self.assertNotIn(time(11, 30), times)
        self.assertNotIn(time(14, 0), times)
        self.assertIn(time(14, 30), times)
        self.assertTrue(all(slot_time > time(14, 0) for slot_time in times))

    def test_booking_api_rejects_a_same_day_past_slot_even_if_sent_manually(self):
        today = timezone.localdate()
        local_now = timezone.make_aware(
            datetime.combine(today, time(14, 0)),
            timezone.get_current_timezone(),
        )
        self.client.force_authenticate(self.customer)

        with patch("services.availability.timezone.now", return_value=local_now):
            response = self.client.post(
                reverse("api_booking_create"),
                {
                    "branch": self.branch.id,
                    "service": self.service.id,
                    "booking_date": today.isoformat(),
                    "booking_time": "11:30:00",
                    "is_pregnant": False,
                },
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("booking_time", response.data)
        self.assertIn("already passed", str(response.data["booking_time"]).lower())

    def test_system_admin_can_create_branch_service_mapping_and_update_hours(self):
        self.client.force_authenticate(self.admin)

        branch_response = self.client.post(
            reverse("api_admin_branch_list_create"),
            {
                "branch_code": "D52B",
                "name": "Day 52 New Branch",
                "address": "100 Admin Road",
                "city": "Pretoria",
                "opening_time": "08:00:00",
                "closing_time": "16:00:00",
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(branch_response.status_code, status.HTTP_201_CREATED)
        branch_id = branch_response.data["id"]

        hours_response = self.client.patch(
            reverse("api_admin_branch_detail", kwargs={"pk": branch_id}),
            {
                "opening_time": "07:30:00",
                "closing_time": "18:00:00",
            },
            format="json",
        )
        self.assertEqual(hours_response.status_code, status.HTTP_200_OK)
        self.assertEqual(str(hours_response.data["opening_time"]), "07:30:00")
        self.assertEqual(str(hours_response.data["closing_time"]), "18:00:00")

        service_response = self.client.post(
            reverse("api_admin_service_list_create"),
            {
                "service_code": "D52N",
                "name": "New Admin Service",
                "description": "Created from the System Admin control plane",
                "average_service_time": 20,
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(service_response.status_code, status.HTTP_201_CREATED)
        service_id = service_response.data["id"]

        mapping_response = self.client.post(
            reverse("api_admin_branch_service_list_create"),
            {
                "branch": branch_id,
                "service": service_id,
                "max_bookings_per_slot": 6,
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(mapping_response.status_code, status.HTTP_201_CREATED)

        saved_branch = Branch.objects.get(pk=branch_id)
        self.assertEqual(saved_branch.opening_time, time(7, 30))
        self.assertEqual(saved_branch.closing_time, time(18, 0))
        self.assertTrue(
            BranchService.objects.filter(
                branch_id=branch_id,
                service_id=service_id,
                max_bookings_per_slot=6,
                is_active=True,
            ).exists()
        )

    def test_admin_hours_update_immediately_changes_generated_appointment_slots(self):
        self.client.force_authenticate(self.admin)
        response = self.client.patch(
            reverse("api_admin_branch_detail", kwargs={"pk": self.branch.id}),
            {"opening_time": "10:00:00", "closing_time": "16:00:00"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.branch.refresh_from_db()
        future_date = timezone.localdate() + timezone.timedelta(days=1)
        slots = get_slot_availability(self.branch, self.service, future_date)
        times = [slot["time"] for slot in slots]

        self.assertEqual(times[0], time(10, 0))
        self.assertEqual(times[-1], time(15, 30))
        self.assertNotIn(time(9, 30), times)

    def test_frontend_contract_removes_stale_check_in_and_refreshes_live_state(self):
        customer_path = Path(finders.find("js/pages/customer-dashboard.js"))
        customer_source = customer_path.read_text(encoding="utf-8")

        self.assertIn("const LIVE_REFRESH_MS = 15000", customer_source)
        self.assertIn("startLiveRefresh()", customer_source)
        self.assertIn("refreshVisibleCustomerState", customer_source)
        self.assertIn("loadAvailability({ silent: true, preserveSelection: true })", customer_source)
        self.assertIn("booking.is_checked_in || FINAL.has(booking.status)", customer_source)
        self.assertIn("bookings = bookings.map", customer_source)
        self.assertIn("That appointment time is no longer available", customer_source)

    def test_admin_frontend_contract_exposes_clear_create_and_update_workflows(self):
        admin_path = Path(finders.find("js/pages/admin-workspace.js"))
        admin_source = admin_path.read_text(encoding="utf-8")

        self.assertIn('textContent = "Create branch"', admin_source)
        self.assertIn('textContent = "Update branch"', admin_source)
        self.assertIn('textContent = "Create service"', admin_source)
        self.assertIn('textContent = "Update service"', admin_source)
        self.assertIn("form.reportValidity()", admin_source)
        self.assertIn("Closing time must be later than opening time.", admin_source)
        self.assertIn("resetFromButton", admin_source)
        self.assertIn("scrollIntoView", admin_source)

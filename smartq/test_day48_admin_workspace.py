from datetime import date, time

from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Profile
from bookings.models import Booking
from branches.models import Branch
from services.models import BranchService, Service


class Day48SystemAdminWorkspaceTests(APITestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username="day48admin",
            password="SafePassword123!",
            first_name="System",
            last_name="Admin",
        )
        Profile.objects.create(
            user=self.admin_user,
            date_of_birth=date(1985, 1, 1),
            gender=Profile.OTHER,
            role=Profile.SYSTEM_ADMIN,
            branch=None,
        )

        self.branch = Branch.objects.create(
            branch_code="ADM48",
            name="Day 48 Admin Branch",
            address="48 Main Street",
            city="Cape Town",
            opening_time=time(8, 0),
            closing_time=time(16, 0),
            is_active=True,
        )
        self.service = Service.objects.create(
            service_code="ADM48S",
            name="Admin Test Service",
            description="Existing service for Day 48 global inspection",
            average_service_time=15,
            is_active=True,
        )
        BranchService.objects.create(
            branch=self.branch,
            service=self.service,
            max_bookings_per_slot=2,
            is_active=True,
        )

        self.customer = User.objects.create_user(
            username="day48customer",
            password="SafePassword123!",
            first_name="Customer",
        )
        Profile.objects.create(
            user=self.customer,
            date_of_birth=date(1998, 4, 4),
            gender=Profile.OTHER,
            role=Profile.CUSTOMER,
        )
        Booking.objects.create(
            user=self.customer,
            branch=self.branch,
            service=self.service,
            booking_date=date.today(),
            booking_time=time(10, 0),
            status=Booking.PENDING,
            source=Booking.ONLINE,
        )

    def authenticate_admin(self):
        self.client.force_authenticate(self.admin_user)

    def test_admin_route_renders_dedicated_day48_workspace(self):
        response = self.client.get(reverse("frontend_admin_workspace"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, "System administration workspace")
        self.assertContains(response, "data-admin-workspace")
        self.assertContains(response, "data-staff-form")
        self.assertContains(response, "data-branch-form")
        self.assertContains(response, "data-service-form")
        self.assertContains(response, "data-mapping-form")
        self.assertContains(response, "data-inspection-branch")
        self.assertNotContains(response, "Call next customer")
        self.assertNotContains(response, "Register guest walk-in")

    def test_day48_admin_assets_are_discoverable(self):
        self.assertIsNotNone(finders.find("css/admin-workspace.css"))
        self.assertIsNotNone(finders.find("js/pages/admin-workspace.js"))

    def test_system_admin_can_read_all_admin_catalogues(self):
        self.authenticate_admin()

        staff = self.client.get(reverse("api_admin_staff_list_create"))
        branches = self.client.get(reverse("api_admin_branch_list_create"))
        services = self.client.get(reverse("api_admin_service_list_create"))
        mappings = self.client.get(reverse("api_admin_branch_service_list_create"))

        self.assertEqual(staff.status_code, status.HTTP_200_OK)
        self.assertEqual(branches.status_code, status.HTTP_200_OK)
        self.assertEqual(services.status_code, status.HTTP_200_OK)
        self.assertEqual(mappings.status_code, status.HTTP_200_OK)
        self.assertTrue(any(item["id"] == self.admin_user.id for item in staff.data))
        self.assertTrue(any(item["id"] == self.branch.id for item in branches.data))
        self.assertTrue(any(item["id"] == self.service.id for item in services.data))

    def test_system_admin_can_create_branch_service_capacity_staff_and_inspect_branch(self):
        self.authenticate_admin()

        branch_response = self.client.post(
            reverse("api_admin_branch_list_create"),
            {
                "branch_code": "ADM48B",
                "name": "Day 48 Created Branch",
                "address": "48 Created Avenue",
                "city": "Johannesburg",
                "opening_time": "08:30:00",
                "closing_time": "17:00:00",
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(branch_response.status_code, status.HTTP_201_CREATED)
        branch_id = branch_response.data["id"]

        service_response = self.client.post(
            reverse("api_admin_service_list_create"),
            {
                "service_code": "ADM48N",
                "name": "Created Admin Service",
                "description": "Created through the Day 48 control-plane contract.",
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
                "max_bookings_per_slot": 3,
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(mapping_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(mapping_response.data["max_bookings_per_slot"], 3)

        staff_response = self.client.post(
            reverse("api_admin_staff_list_create"),
            {
                "username": "day48reception",
                "password": "SafePassword123!",
                "first_name": "Day",
                "last_name": "Reception",
                "email": "day48@example.com",
                "date_of_birth": "1994-05-05",
                "gender": Profile.OTHER,
                "disability_status": False,
                "role": Profile.RECEPTIONIST,
                "branch": branch_id,
            },
            format="json",
        )
        self.assertEqual(staff_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(staff_response.data["branch_id"], branch_id)
        self.assertEqual(staff_response.data["role"], Profile.RECEPTIONIST)

        dashboard_response = self.client.get(
            reverse("api_branch_manager_dashboard", args=[branch_id])
        )
        self.assertEqual(dashboard_response.status_code, status.HTTP_200_OK)
        self.assertEqual(dashboard_response.data["branch"]["id"], branch_id)
        self.assertIn("customers", dashboard_response.data)
        self.assertIn("counters", dashboard_response.data)

    def test_admin_staff_role_branch_invariants_remain_backend_owned(self):
        self.authenticate_admin()

        receptionist_without_branch = self.client.post(
            reverse("api_admin_staff_list_create"),
            {
                "username": "invalidreception",
                "password": "SafePassword123!",
                "date_of_birth": "1990-01-01",
                "gender": Profile.OTHER,
                "disability_status": False,
                "role": Profile.RECEPTIONIST,
                "branch": None,
            },
            format="json",
        )
        self.assertEqual(receptionist_without_branch.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("branch", receptionist_without_branch.data)

        admin_with_branch = self.client.post(
            reverse("api_admin_staff_list_create"),
            {
                "username": "invalidadmin",
                "password": "SafePassword123!",
                "date_of_birth": "1990-01-01",
                "gender": Profile.OTHER,
                "disability_status": False,
                "role": Profile.SYSTEM_ADMIN,
                "branch": self.branch.id,
            },
            format="json",
        )
        self.assertEqual(admin_with_branch.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("branch", admin_with_branch.data)

    def test_system_admin_cannot_deactivate_own_active_session_account(self):
        self.authenticate_admin()

        response = self.client.patch(
            reverse("api_admin_staff_activation", args=[self.admin_user.id]),
            {"is_active": False},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.admin_user.refresh_from_db()
        self.assertTrue(self.admin_user.is_active)

    def test_customer_cannot_use_system_admin_catalogues(self):
        self.client.force_authenticate(self.customer)

        responses = [
            self.client.get(reverse("api_admin_staff_list_create")),
            self.client.get(reverse("api_admin_branch_list_create")),
            self.client.get(reverse("api_admin_service_list_create")),
            self.client.get(reverse("api_admin_branch_service_list_create")),
        ]

        for response in responses:
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

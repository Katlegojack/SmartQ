from datetime import date, time

from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Profile
from branches.models import Branch
from counters.models import Counter
from queues.models import QueueTicket


class Day47BranchManagerWorkspaceTests(APITestCase):
    def setUp(self):
        self.branch = Branch.objects.create(
            branch_code="MGR47",
            name="Day 47 Manager Branch",
            address="47 Main Street",
            city="Kimberley",
            opening_time=time(8, 0),
            closing_time=time(16, 0),
            is_active=True,
        )
        self.other_branch = Branch.objects.create(
            branch_code="MGR47B",
            name="Other Manager Branch",
            address="48 Main Street",
            city="Pretoria",
            opening_time=time(8, 0),
            closing_time=time(16, 0),
            is_active=True,
        )

        self.manager = User.objects.create_user(
            username="day47manager",
            password="SafePassword123!",
            first_name="Mpho",
        )
        Profile.objects.create(
            user=self.manager,
            date_of_birth=date(1988, 2, 2),
            gender=Profile.OTHER,
            role=Profile.BRANCH_MANAGER,
            branch=self.branch,
        )

        self.counter_staff = User.objects.create_user(
            username="day47counter",
            password="SafePassword123!",
            first_name="Kabelo",
            last_name="Staff",
        )
        Profile.objects.create(
            user=self.counter_staff,
            date_of_birth=date(1992, 4, 4),
            gender=Profile.OTHER,
            role=Profile.COUNTER_STAFF,
            branch=self.branch,
        )

        self.other_staff = User.objects.create_user(
            username="day47otherstaff",
            password="SafePassword123!",
        )
        Profile.objects.create(
            user=self.other_staff,
            date_of_birth=date(1991, 5, 5),
            gender=Profile.OTHER,
            role=Profile.COUNTER_STAFF,
            branch=self.other_branch,
        )

        self.counter = Counter.objects.create(
            branch=self.branch,
            counter_number="1",
            queue_type=QueueTicket.GENERAL,
            status=Counter.CLOSED,
        )

    def authenticate_manager(self):
        self.client.force_authenticate(self.manager)

    def test_manager_route_renders_dedicated_day47_workspace(self):
        response = self.client.get(reverse("frontend_manager_workspace"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, "Branch manager workspace")
        self.assertContains(response, "data-manager-workspace")
        self.assertContains(response, "data-dashboard-date")
        self.assertContains(response, "data-counter-body")
        self.assertNotContains(response, "System administration")

    def test_day47_manager_assets_are_discoverable(self):
        self.assertIsNotNone(finders.find("css/manager-workspace.css"))
        self.assertIsNotNone(finders.find("js/pages/manager-workspace.js"))

    def test_manager_can_read_own_branch_dashboard(self):
        self.authenticate_manager()

        response = self.client.get(
            reverse("api_branch_manager_dashboard", args=[self.branch.id])
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["branch"]["id"], self.branch.id)
        self.assertIn("customers", response.data)
        self.assertIn("queue_statistics", response.data)
        self.assertIn("services", response.data)
        self.assertIn("counters", response.data)

    def test_manager_counter_staff_directory_is_own_branch_and_counter_staff_only(self):
        receptionist = User.objects.create_user(
            username="day47reception",
            password="SafePassword123!",
        )
        Profile.objects.create(
            user=receptionist,
            date_of_birth=date(1990, 1, 1),
            gender=Profile.OTHER,
            role=Profile.RECEPTIONIST,
            branch=self.branch,
        )
        self.authenticate_manager()

        response = self.client.get(
            reverse("api_branch_counter_staff_list", args=[self.branch.id])
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.counter_staff.id)
        self.assertEqual(response.data[0]["display_name"], "Kabelo Staff")
        self.assertIsNone(response.data[0]["assigned_counter_id"])

    def test_manager_cannot_read_other_branch_counter_staff_directory(self):
        self.authenticate_manager()

        response = self.client.get(
            reverse("api_branch_counter_staff_list", args=[self.other_branch.id])
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_customer_cannot_read_manager_counter_staff_directory(self):
        customer = User.objects.create_user(
            username="day47customer",
            password="SafePassword123!",
        )
        Profile.objects.create(
            user=customer,
            date_of_birth=date(1999, 6, 6),
            gender=Profile.OTHER,
            role=Profile.CUSTOMER,
        )
        self.client.force_authenticate(customer)

        response = self.client.get(
            reverse("api_branch_counter_staff_list", args=[self.branch.id])
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_can_list_assign_verify_and_unassign_counter_staff(self):
        self.authenticate_manager()

        directory_before = self.client.get(
            reverse("api_branch_counter_staff_list", args=[self.branch.id])
        )
        self.assertEqual(directory_before.status_code, status.HTTP_200_OK)
        self.assertIsNone(directory_before.data[0]["assigned_counter_id"])

        assign_response = self.client.post(
            reverse("api_counter_assign_staff", args=[self.counter.id]),
            {"staff_user_id": self.counter_staff.id},
            format="json",
        )
        self.assertEqual(assign_response.status_code, status.HTTP_200_OK)
        self.assertEqual(assign_response.data["assigned_staff"], self.counter_staff.id)

        directory_after = self.client.get(
            reverse("api_branch_counter_staff_list", args=[self.branch.id])
        )
        self.assertEqual(directory_after.data[0]["assigned_counter_id"], self.counter.id)
        self.assertEqual(directory_after.data[0]["assigned_counter_number"], "1")

        dashboard = self.client.get(
            reverse("api_branch_manager_dashboard", args=[self.branch.id])
        )
        counter_row = dashboard.data["counters"]["counters"][0]
        self.assertEqual(counter_row["assigned_staff_id"], self.counter_staff.id)
        self.assertEqual(counter_row["assigned_staff_username"], self.counter_staff.username)

        unassign_response = self.client.post(
            reverse("api_counter_unassign_staff", args=[self.counter.id])
        )
        self.assertEqual(unassign_response.status_code, status.HTTP_200_OK)
        self.assertIsNone(unassign_response.data["assigned_staff"])

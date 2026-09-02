from datetime import date, time

from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Profile
from branches.models import Branch
from services.models import BranchService, Service


class Day45ReceptionWorkspaceTests(APITestCase):
    def setUp(self):
        self.branch = Branch.objects.create(
            branch_code="REC45",
            name="Day 45 Reception Branch",
            address="45 Main Street",
            city="Kimberley",
            opening_time=time(8, 0),
            closing_time=time(16, 0),
            is_active=True,
        )
        self.service = Service.objects.create(
            service_code="REC45S",
            name="Reception Service",
            description="Day 45 reception integration service",
            average_service_time=15,
            is_active=True,
        )
        BranchService.objects.create(
            branch=self.branch,
            service=self.service,
            max_bookings_per_slot=4,
            is_active=True,
        )
        self.receptionist = User.objects.create_user(
            username="day45reception",
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

    def authenticate(self):
        self.client.force_authenticate(self.receptionist)

    def test_reception_route_renders_dedicated_day45_workspace(self):
        response = self.client.get(reverse("frontend_reception_workspace"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reception desk")
        self.assertContains(response, "data-reception-workspace")
        self.assertContains(response, "data-search-form")
        self.assertContains(response, "data-search-results")
        self.assertContains(response, "data-queue-refresh")
        self.assertContains(response, "data-walkin-form")
        self.assertContains(response, "Reception never chooses General or Priority")
        self.assertNotContains(response, "Manager analytics")
        self.assertNotContains(response, "System administration")

    def test_day45_reception_assets_are_discoverable(self):
        self.assertIsNotNone(finders.find("css/reception-workspace.css"))
        self.assertIsNotNone(finders.find("js/pages/reception-workspace.js"))

    def test_receptionist_can_load_only_services_offered_at_assigned_branch(self):
        self.authenticate()

        response = self.client.get(
            reverse("api_branch_service_list", args=[self.branch.id])
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data)

    def test_receptionist_can_create_guest_walk_in_and_queue_confirmation(self):
        self.authenticate()

        response = self.client.post(
            reverse("api_reception_guest_walk_in"),
            {
                "full_name": "Walk In Guest",
                "phone_number": "0712345678",
                "date_of_birth": "1990-04-10",
                "gender": "other",
                "disability_status": False,
                "is_pregnant": False,
                "service": self.service.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["branch"], self.branch.id)
        self.assertEqual(response.data["source"], "walk_in")
        self.assertTrue(response.data["is_checked_in"])
        self.assertEqual(response.data["queue_ticket"]["status"], "waiting")
        self.assertTrue(response.data["queue_ticket"]["queue_number"])

        queue_response = self.client.get(
            reverse("api_branch_waiting_queue", args=[self.branch.id])
        )
        self.assertEqual(queue_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(queue_response.data), 1)
        self.assertEqual(queue_response.data[0]["customer_name"], "Walk In Guest")

    def test_customer_role_cannot_use_reception_walk_in_api(self):
        customer = User.objects.create_user(
            username="day45customer",
            password="SafePassword123!",
        )
        Profile.objects.create(
            user=customer,
            date_of_birth=date(1998, 1, 1),
            gender=Profile.OTHER,
            role=Profile.CUSTOMER,
        )
        self.client.force_authenticate(customer)

        response = self.client.post(
            reverse("api_reception_guest_walk_in"),
            {
                "full_name": "Blocked Guest",
                "date_of_birth": "1990-04-10",
                "gender": "other",
                "service": self.service.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

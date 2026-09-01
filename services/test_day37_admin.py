from datetime import date, time

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounts.models import Profile
from branches.models import Branch

from .models import BranchService, Service


class SystemAdminServiceConfigurationTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username="sysadmin",
            password="Strong-Test-Pass-482!",
        )
        Profile.objects.create(
            user=self.admin,
            date_of_birth=date(1985, 1, 1),
            gender=Profile.OTHER,
            role=Profile.SYSTEM_ADMIN,
        )
        self.customer = User.objects.create_user(
            username="customer",
            password="Strong-Test-Pass-482!",
        )
        Profile.objects.create(
            user=self.customer,
            date_of_birth=date(1995, 1, 1),
            gender=Profile.OTHER,
            role=Profile.CUSTOMER,
        )
        self.branch = Branch.objects.create(
            branch_code="KIM001",
            name="Kimberley Branch",
            address="Civic Centre",
            city="Kimberley",
            opening_time=time(8, 0),
            closing_time=time(16, 30),
        )

    def service_payload(self, **overrides):
        payload = {
            "service_code": "PASS001",
            "name": "Passport Collection",
            "description": "Collect a completed passport.",
            "average_service_time": 10,
            "is_active": True,
        }
        payload.update(overrides)
        return payload

    def test_system_admin_can_create_service(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            reverse("api_admin_service_list_create"),
            self.service_payload(),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Service.objects.filter(service_code="PASS001").exists())

    def test_customer_cannot_create_service(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.post(
            reverse("api_admin_service_list_create"),
            self.service_payload(),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_service_duration_must_be_positive(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            reverse("api_admin_service_list_create"),
            self.service_payload(average_service_time=0),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("average_service_time", response.data)

    def test_system_admin_can_create_branch_service_capacity_mapping(self):
        service = Service.objects.create(
            service_code="PASS001",
            name="Passport Collection",
            description="Collect passport",
            average_service_time=10,
        )
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            reverse("api_admin_branch_service_list_create"),
            {
                "branch": self.branch.id,
                "service": service.id,
                "max_bookings_per_slot": 3,
                "is_active": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        mapping = BranchService.objects.get(branch=self.branch, service=service)
        self.assertEqual(mapping.max_bookings_per_slot, 3)

    def test_active_mapping_rejects_inactive_service(self):
        service = Service.objects.create(
            service_code="OLD001",
            name="Old Service",
            description="Inactive",
            average_service_time=10,
            is_active=False,
        )
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            reverse("api_admin_branch_service_list_create"),
            {
                "branch": self.branch.id,
                "service": service.id,
                "max_bookings_per_slot": 1,
                "is_active": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("service", response.data)

    def test_deactivated_service_disappears_from_public_catalogue(self):
        service = Service.objects.create(
            service_code="PASS001",
            name="Passport Collection",
            description="Collect passport",
            average_service_time=10,
        )
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            reverse("api_admin_service_detail", kwargs={"pk": service.pk}),
            {"is_active": False},
            format="json",
        )
        self.client.force_authenticate(user=None)
        public_response = self.client.get(reverse("api_service_list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(public_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(public_response.data), 0)

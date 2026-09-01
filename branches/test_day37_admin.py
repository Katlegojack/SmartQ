from datetime import date

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounts.models import Profile

from .models import Branch


class SystemAdminBranchManagementTests(APITestCase):
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

    def branch_payload(self, **overrides):
        payload = {
            "branch_code": "KIM001",
            "name": "Kimberley Branch",
            "address": "Civic Centre",
            "city": "Kimberley",
            "opening_time": "08:00:00",
            "closing_time": "16:30:00",
            "is_active": True,
        }
        payload.update(overrides)
        return payload

    def test_system_admin_can_create_branch(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            reverse("api_admin_branch_list_create"),
            self.branch_payload(),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Branch.objects.filter(branch_code="KIM001").exists())

    def test_customer_cannot_create_branch(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.post(
            reverse("api_admin_branch_list_create"),
            self.branch_payload(),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Branch.objects.filter(branch_code="KIM001").exists())

    def test_branch_hours_must_be_ordered(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            reverse("api_admin_branch_list_create"),
            self.branch_payload(opening_time="17:00:00", closing_time="08:00:00"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("closing_time", response.data)

    def test_deactivated_branch_disappears_from_public_catalogue(self):
        branch = Branch.objects.create(
            branch_code="KIM001",
            name="Kimberley Branch",
            address="Civic Centre",
            city="Kimberley",
            opening_time="08:00:00",
            closing_time="16:30:00",
        )
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            reverse("api_admin_branch_detail", kwargs={"pk": branch.pk}),
            {"is_active": False},
            format="json",
        )
        self.client.force_authenticate(user=None)
        public_response = self.client.get(reverse("api_branch_list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(public_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(public_response.data), 0)

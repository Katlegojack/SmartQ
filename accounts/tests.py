from datetime import date

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from .models import Profile


class AccountAuthenticationAPITests(APITestCase):
    """Regression tests for Day 29 customer registration and session authentication."""

    def setUp(self):
        self.client = APIClient()
        self.registration_payload = {
            "username": "newcustomer",
            "password": "Strong-Test-Pass-482!",
            "first_name": "New",
            "last_name": "Customer",
            "email": "customer@example.com",
            "date_of_birth": "1998-05-20",
            "gender": Profile.OTHER,
            "disability_status": False,
        }

    def test_public_registration_creates_customer_profile(self):
        response = self.client.post(
            reverse("api_register"),
            self.registration_payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(username="newcustomer")
        self.assertTrue(user.check_password(self.registration_payload["password"]))
        self.assertEqual(user.profile.role, Profile.CUSTOMER)
        self.assertIsNone(user.profile.branch)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_registration_cannot_self_assign_system_admin_role(self):
        """Caller-supplied privilege fields must never create a staff account."""
        payload = {
            **self.registration_payload,
            "role": Profile.SYSTEM_ADMIN,
            "is_staff": True,
            "is_superuser": True,
            "branch": 999,
        }

        response = self.client.post(reverse("api_register"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(username="newcustomer")
        self.assertEqual(user.profile.role, Profile.CUSTOMER)
        self.assertIsNone(user.profile.branch)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_duplicate_username_is_rejected(self):
        User.objects.create_user(username="newcustomer", password="Existing-Pass-44!")

        response = self.client.post(
            reverse("api_register"),
            self.registration_payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("username", response.data)

    def test_login_starts_session_and_me_returns_role(self):
        user = User.objects.create_user(
            username="customer",
            password="Strong-Test-Pass-482!",
            first_name="Test",
            last_name="Customer",
        )
        Profile.objects.create(
            user=user,
            date_of_birth=date(1995, 1, 1),
            gender=Profile.OTHER,
            role=Profile.CUSTOMER,
        )

        login_response = self.client.post(
            reverse("api_login"),
            {
                "username": "customer",
                "password": "Strong-Test-Pass-482!",
            },
            format="json",
        )
        me_response = self.client.get(reverse("api_current_account"))

        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertEqual(me_response.status_code, status.HTTP_200_OK)
        self.assertEqual(me_response.data["username"], "customer")
        self.assertEqual(me_response.data["role"], Profile.CUSTOMER)

    def test_invalid_login_is_rejected(self):
        user = User.objects.create_user(
            username="customer",
            password="Strong-Test-Pass-482!",
        )
        Profile.objects.create(
            user=user,
            date_of_birth=date(1995, 1, 1),
            gender=Profile.OTHER,
            role=Profile.CUSTOMER,
        )

        response = self.client.post(
            reverse("api_login"),
            {"username": "customer", "password": "wrong-password"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_ends_session(self):
        user = User.objects.create_user(
            username="customer",
            password="Strong-Test-Pass-482!",
        )
        Profile.objects.create(
            user=user,
            date_of_birth=date(1995, 1, 1),
            gender=Profile.OTHER,
            role=Profile.CUSTOMER,
        )
        self.client.login(username="customer", password="Strong-Test-Pass-482!")

        logout_response = self.client.post(reverse("api_logout"))
        me_response = self.client.get(reverse("api_current_account"))

        self.assertEqual(logout_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertIn(
            me_response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )

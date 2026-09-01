from datetime import date, time

from django.contrib.auth.models import User
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from branches.models import Branch

from .models import Profile


class Day37AccountSecurityTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="customer",
            password="Original-Strong-Pass-482!",
        )
        Profile.objects.create(
            user=self.user,
            date_of_birth=date(1995, 1, 1),
            gender=Profile.OTHER,
            role=Profile.CUSTOMER,
        )

    def test_authenticated_user_can_change_password_and_keep_current_session(self):
        self.client.login(
            username="customer",
            password="Original-Strong-Pass-482!",
        )

        response = self.client.post(
            reverse("api_change_password"),
            {
                "current_password": "Original-Strong-Pass-482!",
                "new_password": "Replacement-Strong-Pass-731!",
            },
            format="json",
        )
        me_response = self.client.get(reverse("api_current_account"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(me_response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Replacement-Strong-Pass-731!"))
        self.assertFalse(self.user.check_password("Original-Strong-Pass-482!"))

    def test_password_change_requires_correct_current_password(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("api_change_password"),
            {
                "current_password": "wrong-password",
                "new_password": "Replacement-Strong-Pass-731!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("current_password", response.data)

    def test_password_change_reuses_django_password_validators(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("api_change_password"),
            {
                "current_password": "Original-Strong-Pass-482!",
                "new_password": "123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_password", response.data)

    def test_login_endpoint_is_throttled_after_repeated_failures(self):
        responses = []
        for _ in range(11):
            responses.append(
                self.client.post(
                    reverse("api_login"),
                    {
                        "username": "customer",
                        "password": "wrong-password",
                    },
                    format="json",
                )
            )

        for response in responses[:10]:
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(responses[10].status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_deactivated_staff_account_cannot_log_in(self):
        branch = Branch.objects.create(
            branch_code="KIM001",
            name="Kimberley Branch",
            address="Civic Centre",
            city="Kimberley",
            opening_time=time(8, 0),
            closing_time=time(16, 30),
        )
        admin = User.objects.create_user(
            username="sysadmin",
            password="Admin-Strong-Pass-482!",
        )
        Profile.objects.create(
            user=admin,
            date_of_birth=date(1985, 1, 1),
            gender=Profile.OTHER,
            role=Profile.SYSTEM_ADMIN,
        )
        staff = User.objects.create_user(
            username="receptionist",
            password="Staff-Strong-Pass-482!",
        )
        Profile.objects.create(
            user=staff,
            date_of_birth=date(1990, 1, 1),
            gender=Profile.OTHER,
            role=Profile.RECEPTIONIST,
            branch=branch,
        )

        self.client.force_authenticate(user=admin)
        deactivate_response = self.client.patch(
            reverse("api_admin_staff_activation", kwargs={"pk": staff.pk}),
            {"is_active": False},
            format="json",
        )

        cache.clear()
        login_client = APIClient()
        login_response = login_client.post(
            reverse("api_login"),
            {
                "username": "receptionist",
                "password": "Staff-Strong-Pass-482!",
            },
            format="json",
        )

        self.assertEqual(deactivate_response.status_code, status.HTTP_200_OK)
        self.assertEqual(login_response.status_code, status.HTTP_401_UNAUTHORIZED)

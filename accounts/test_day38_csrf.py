from datetime import date

from django.contrib.auth.models import User
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from .models import Profile


class SessionLoginCSRFTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient(enforce_csrf_checks=True)
        self.user = User.objects.create_user(
            username="csrf.customer",
            password="Strong-Test-Pass-482!",
        )
        Profile.objects.create(
            user=self.user,
            date_of_birth=date(1995, 1, 1),
            gender=Profile.OTHER,
            role=Profile.CUSTOMER,
        )
        self.login_payload = {
            "username": "csrf.customer",
            "password": "Strong-Test-Pass-482!",
        }

    def test_csrf_endpoint_sets_cookie_and_returns_token(self):
        response = self.client.get(reverse("api_csrf_token"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("csrfToken", response.data)
        self.assertTrue(response.data["csrfToken"])
        self.assertIn("csrftoken", response.cookies)

    def test_browser_login_without_csrf_header_is_rejected(self):
        self.client.get(reverse("api_csrf_token"))

        response = self.client.post(
            reverse("api_login"),
            self.login_payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_browser_login_succeeds_with_bootstrapped_csrf_token(self):
        token_response = self.client.get(reverse("api_csrf_token"))
        csrf_token = token_response.data["csrfToken"]

        login_response = self.client.post(
            reverse("api_login"),
            self.login_payload,
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        me_response = self.client.get(reverse("api_current_account"))

        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertEqual(me_response.status_code, status.HTTP_200_OK)
        self.assertEqual(me_response.data["username"], "csrf.customer")

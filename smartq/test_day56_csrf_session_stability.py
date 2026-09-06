import json
from datetime import date, time
from pathlib import Path

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import Profile
from branches.models import Branch


class Day56CsrfSessionStabilityTests(TestCase):
    """Reproduce and protect the CSRF/session failures seen during live role testing."""

    PASSWORD = "SafePassword123!"

    def repo_text(self, path):
        return (Path(__file__).resolve().parents[1] / path).read_text(encoding="utf-8")

    def setUp(self):
        self.branch = Branch.objects.create(
            branch_code="D56",
            name="Day 56 Salon",
            address="56 Stability Road",
            city="Pretoria",
            opening_time=time(8, 0),
            closing_time=time(17, 0),
            is_active=True,
        )
        self.admin = User.objects.create_user(
            username="day56_admin",
            password=self.PASSWORD,
            first_name="Day56",
            last_name="Admin",
        )
        Profile.objects.create(
            user=self.admin,
            date_of_birth=date(1990, 1, 1),
            gender=Profile.OTHER,
            role=Profile.SYSTEM_ADMIN,
            branch=None,
        )

    def login_admin(self, browser):
        token = browser.get(reverse("api_csrf_token")).json()["csrfToken"]
        response = browser.post(
            reverse("api_login"),
            data=json.dumps(
                {
                    "username": self.admin.username,
                    "password": self.PASSWORD,
                    "role": Profile.SYSTEM_ADMIN,
                }
            ),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 200)
        return token

    def staff_payload(self, username, role):
        return {
            "username": username,
            "password": self.PASSWORD,
            "first_name": username.title(),
            "last_name": "Operator",
            "email": f"{username}@example.com",
            "date_of_birth": "1992-06-12",
            "gender": Profile.OTHER,
            "disability_status": False,
            "role": role,
            "branch": self.branch.id,
        }

    def test_api_csrf_failure_is_json_not_django_debug_html(self):
        browser = Client(enforce_csrf_checks=True)
        stale_token = self.login_admin(browser)

        # Login rotates Django's CSRF secret. Reusing the pre-login token now
        # reproduces the exact live failure that previously rendered a huge 403 page.
        response = browser.post(
            reverse("api_login"),
            data=json.dumps(
                {
                    "username": self.admin.username,
                    "password": self.PASSWORD,
                    "role": Profile.SYSTEM_ADMIN,
                }
            ),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=stale_token,
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(response["Content-Type"].startswith("application/json"))
        self.assertTrue(response.json()["csrfFailure"])
        self.assertNotIn("<!DOCTYPE html>", response.content.decode("utf-8"))

    def test_csrf_endpoint_is_explicitly_non_cacheable(self):
        response = self.client.get(reverse("api_csrf_token"))
        self.assertEqual(response.status_code, 200)
        cache_control = response.headers.get("Cache-Control", "")
        self.assertIn("no-store", cache_control)
        self.assertIn("no-cache", cache_control)

    def test_stale_admin_csrf_is_recoverable_and_manager_receptionist_creation_is_valid(self):
        browser = Client(enforce_csrf_checks=True)
        stale_token = self.login_admin(browser)

        manager_payload = self.staff_payload("day56_manager", Profile.BRANCH_MANAGER)
        stale_response = browser.post(
            reverse("api_admin_staff_list_create"),
            data=json.dumps(manager_payload),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=stale_token,
        )
        self.assertEqual(stale_response.status_code, 403)
        self.assertIn("CSRF Failed:", stale_response.json()["detail"])

        fresh_token = browser.get(reverse("api_csrf_token")).json()["csrfToken"]
        manager_response = browser.post(
            reverse("api_admin_staff_list_create"),
            data=json.dumps(manager_payload),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=fresh_token,
        )
        self.assertEqual(manager_response.status_code, 201)
        self.assertEqual(manager_response.json()["role"], Profile.BRANCH_MANAGER)
        self.assertEqual(manager_response.json()["branch_id"], self.branch.id)

        receptionist_response = browser.post(
            reverse("api_admin_staff_list_create"),
            data=json.dumps(self.staff_payload("day56_reception", Profile.RECEPTIONIST)),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=fresh_token,
        )
        self.assertEqual(receptionist_response.status_code, 201)
        self.assertEqual(receptionist_response.json()["role"], Profile.RECEPTIONIST)
        self.assertEqual(receptionist_response.json()["branch_id"], self.branch.id)

    def test_new_manager_and_receptionist_can_log_in_with_their_exact_roles(self):
        for username, role in [
            ("role56_manager", Profile.BRANCH_MANAGER),
            ("role56_reception", Profile.RECEPTIONIST),
        ]:
            user = User.objects.create_user(username=username, password=self.PASSWORD)
            Profile.objects.create(
                user=user,
                date_of_birth=date(1992, 6, 12),
                gender=Profile.OTHER,
                role=role,
                branch=self.branch,
            )

            browser = Client(enforce_csrf_checks=True)
            token = browser.get(reverse("api_csrf_token")).json()["csrfToken"]
            login = browser.post(
                reverse("api_login"),
                data=json.dumps(
                    {"username": username, "password": self.PASSWORD, "role": role}
                ),
                content_type="application/json",
                HTTP_X_CSRFTOKEN=token,
            )
            self.assertEqual(login.status_code, 200)
            self.assertEqual(login.json()["user"]["role"], role)

            me = browser.get(reverse("api_current_account"))
            self.assertEqual(me.status_code, 200)
            self.assertEqual(me.json()["role"], role)
            self.assertEqual(me.json()["branch_id"], self.branch.id)

    def test_frontend_recognises_drf_csrf_json_and_retries_without_fake_expiry(self):
        legacy = self.repo_text("static/js/api/client.js")
        react = self.repo_text("frontend/src/api.ts")
        settings = self.repo_text("smartq/settings.py")
        csrf_view = self.repo_text("smartq/csrf.py")

        for source in [legacy, react]:
            self.assertIn('"CSRF Failed:"', source)
            self.assertIn('cache: "no-store"', source)
            self.assertIn("retry < 2", source)
            self.assertIn("LOGOUT_PATH", source)
            self.assertIn("isCsrfFailure", source)

        self.assertIn('CSRF_FAILURE_VIEW = "smartq.csrf.csrf_failure"', settings)
        self.assertIn('"csrfFailure": True', csrf_view)
        self.assertIn('request.path.startswith("/api/")', csrf_view)

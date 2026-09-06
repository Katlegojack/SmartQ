import json
from datetime import date
from pathlib import Path

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import Profile


class Day55AuthSessionUiTests(TestCase):
    """Protect login, CSRF recovery, logout and public UI behaviour."""

    def repo_text(self, path):
        return (Path(__file__).resolve().parents[1] / path).read_text(encoding="utf-8")

    def setUp(self):
        self.user = User.objects.create_user(
            username="day55_customer",
            password="SafePassword123!",
            first_name="Day55",
        )
        Profile.objects.create(
            user=self.user,
            date_of_birth=date(1995, 1, 1),
            gender=Profile.OTHER,
            role=Profile.CUSTOMER,
        )

    def test_django_rotates_csrf_after_login_and_fresh_token_logs_out(self):
        client = Client(enforce_csrf_checks=True)
        csrf_response = client.get(reverse("api_csrf_token"))
        self.assertEqual(csrf_response.status_code, 200)
        pre_login_token = csrf_response.json()["csrfToken"]

        login_response = client.post(
            reverse("api_login"),
            data=json.dumps(
                {
                    "username": "day55_customer",
                    "password": "SafePassword123!",
                    "role": Profile.CUSTOMER,
                }
            ),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=pre_login_token,
        )
        self.assertEqual(login_response.status_code, 200)

        stale_logout = client.post(
            reverse("api_logout"),
            data="{}",
            content_type="application/json",
            HTTP_X_CSRFTOKEN=pre_login_token,
        )
        self.assertEqual(stale_logout.status_code, 403)

        fresh_token = client.get(reverse("api_csrf_token")).json()["csrfToken"]
        fresh_logout = client.post(
            reverse("api_logout"),
            data="{}",
            content_type="application/json",
            HTTP_X_CSRFTOKEN=fresh_token,
        )
        self.assertEqual(fresh_logout.status_code, 204)

    def test_browser_clients_refresh_stale_csrf_and_never_surface_html_errors(self):
        legacy_client = self.repo_text("static/js/api/client.js")
        react_client = self.repo_text("frontend/src/api.ts")
        react_auth = self.repo_text("frontend/src/auth.ts")

        for source in [legacy_client, react_client]:
            self.assertIn("csrfFailure", source)
            self.assertIn("CSRF verification failed", source)
            self.assertIn("contentType.includes(\"text/html\")", source)
            self.assertIn("clearCsrfToken();", source)

        self.assertIn("ensureCsrfToken({ force: true })", legacy_client)
        self.assertIn("ensureCsrfToken(true)", react_client)
        self.assertIn("clearCsrfToken();\n  return result.user;", react_auth)

    def test_logout_hard_navigates_after_server_session_is_destroyed(self):
        components = self.repo_text("frontend/src/components.tsx")

        self.assertIn("await logout();", components)
        self.assertIn("queryClient.clear();", components)
        self.assertIn("window.location.replace", components)
        self.assertIn('disabled={logoutBusy}>Log out</button>', components)
        self.assertIn("Smart Q could not log you out. Please try again.", components)

    def test_login_is_compact_blue_and_keeps_every_role_choice(self):
        response = self.client.get(reverse("frontend_login"))
        self.assertEqual(response.status_code, 200)

        for role in [
            "customer",
            "receptionist",
            "counter_staff",
            "branch_manager",
            "system_admin",
        ]:
            self.assertContains(response, f'value="{role}"')

        self.assertNotContains(response, "Run the queue.")
        self.assertNotContains(response, "Select your Smart Q role, then enter your credentials.")

        login_css = self.repo_text("static/css/login.css")
        polish = self.repo_text("frontend/src/polish.css")
        react_shell = self.repo_text("templates/frontend/react_app.html")

        self.assertIn("width:min(100%,780px)", login_css)
        self.assertIn("--brand: #2878c8", polish)
        self.assertIn("--nav: #0d2e4b", polish)
        self.assertIn(".auth-brand", polish)
        self.assertIn("display: none", polish)
        self.assertNotIn("The Day 41-52 Django frontend tests", react_shell)

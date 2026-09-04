from pathlib import Path

from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import Profile


class Day42FrontendAuthenticationTests(TestCase):
    def test_public_authentication_pages_render_shared_assets(self):
        login = self.client.get(reverse("frontend_login"))
        staff_login = self.client.get(reverse("frontend_staff_login"))
        register = self.client.get(reverse("frontend_register"))

        self.assertEqual(login.status_code, 200)
        self.assertEqual(staff_login.status_code, 200)
        self.assertEqual(register.status_code, 200)
        self.assertContains(login, "Customer sign in")
        self.assertContains(login, "join a live queue")
        self.assertContains(staff_login, "Staff sign in")
        self.assertContains(staff_login, "Receptionists, Counter Staff, Branch Managers and System Administrators")
        self.assertContains(register, "Customer registration")
        self.assertContains(login, "/static/css/auth-shell.css")
        self.assertContains(login, "/static/js/pages/login.js")
        self.assertContains(staff_login, "/static/js/pages/login.js")
        self.assertContains(register, "/static/js/pages/register.js")

    def test_registration_frontend_does_not_auto_login_new_customer(self):
        register_path = Path(finders.find("js/pages/register.js"))
        source = register_path.read_text(encoding="utf-8")

        self.assertIn('await registerCustomer(payload)', source)
        self.assertIn('/login/?created=1', source)
        self.assertNotIn("loginAccount(", source)
        self.assertNotIn("Opening your workspace", source)

    def test_role_workspace_routes_render_expected_role_contract(self):
        routes = {
            "frontend_customer_workspace": "customer",
            "frontend_reception_workspace": "receptionist",
            "frontend_counter_workspace": "counter_staff",
            "frontend_manager_workspace": "branch_manager",
            "frontend_admin_workspace": "system_admin",
        }

        for route_name, role in routes.items():
            with self.subTest(route=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, f'data-expected-role="{role}"')
                self.assertContains(response, "/static/js/pages/app-shell.js")

    def test_day42_module_assets_are_discoverable(self):
        assets = [
            "css/auth-shell.css",
            "js/api/client.js",
            "js/auth/session.js",
            "js/pages/home.js",
            "js/pages/login.js",
            "js/pages/register.js",
            "js/pages/app-shell.js",
        ]
        for asset in assets:
            with self.subTest(asset=asset):
                self.assertIsNotNone(finders.find(asset))

    def test_frontend_api_client_targets_existing_account_contract(self):
        client_path = Path(finders.find("js/api/client.js"))
        session_path = Path(finders.find("js/auth/session.js"))
        combined = client_path.read_text(encoding="utf-8") + session_path.read_text(encoding="utf-8")

        for endpoint in [
            "/api/v1/accounts/csrf/",
            "/api/v1/accounts/me/",
            "/api/v1/accounts/login/",
            "/api/v1/accounts/logout/",
            "/api/v1/accounts/register/",
            "/api/v1/accounts/change-password/",
        ]:
            with self.subTest(endpoint=endpoint):
                self.assertIn(endpoint, combined)

    def test_session_login_me_and_logout_support_frontend_flow(self):
        user = User.objects.create_user(username="day42customer", password="SafePassword123!")
        Profile.objects.create(
            user=user,
            date_of_birth="1995-05-12",
            gender=Profile.OTHER,
            role=Profile.CUSTOMER,
        )
        browser = Client(enforce_csrf_checks=True)

        csrf_response = browser.get(reverse("api_csrf_token"))
        self.assertEqual(csrf_response.status_code, 200)
        csrf_token = csrf_response.json()["csrfToken"]

        login_response = browser.post(
            reverse("api_login"),
            {"username": "day42customer", "password": "SafePassword123!"},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(login_response.status_code, 200)
        self.assertEqual(login_response.json()["user"]["role"], Profile.CUSTOMER)

        me_response = browser.get(reverse("api_current_account"))
        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.json()["username"], "day42customer")

        refreshed_csrf = browser.get(reverse("api_csrf_token")).json()["csrfToken"]
        logout_response = browser.post(
            reverse("api_logout"),
            HTTP_X_CSRFTOKEN=refreshed_csrf,
        )
        self.assertEqual(logout_response.status_code, 204)

    def test_public_frontend_contains_no_emoji_style_interface_copy(self):
        for route_name in ["frontend_home", "frontend_login", "frontend_staff_login", "frontend_register"]:
            response = self.client.get(reverse(route_name))
            content = response.content.decode("utf-8")
            for banned in ["🚀", "✨", "🎉", "✅", "👤", "📊", "🔐"]:
                self.assertNotIn(banned, content)

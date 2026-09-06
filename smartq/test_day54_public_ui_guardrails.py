from pathlib import Path

from django.test import TestCase
from django.urls import reverse


class Day54PublicUiGuardrailTests(TestCase):
    """Protect the approved Smart Q public identity and clean role workspaces."""

    def repo_text(self, path):
        return (Path(__file__).resolve().parents[1] / path).read_text(encoding="utf-8")

    def test_landing_page_keeps_approved_vision_and_mission(self):
        response = self.client.get(reverse("frontend_home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "SMART Q")
        self.assertContains(response, "Where Time Meets Priority")
        self.assertContains(response, "Vision")
        self.assertContains(response, "Mission")
        self.assertContains(response, "Make waiting predictable, transparent and fair.")
        self.assertContains(response, "Give people their time back.")
        self.assertContains(response, 'href="/login/"')
        self.assertContains(response, 'href="/register/"')
        self.assertNotContains(response, 'id="smartq-react-root"')

    def test_login_keeps_all_role_choices(self):
        for route_name in ["frontend_login", "frontend_staff_login"]:
            with self.subTest(route=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                for role in [
                    "customer",
                    "receptionist",
                    "counter_staff",
                    "branch_manager",
                    "system_admin",
                ]:
                    self.assertContains(response, f'value="{role}"')
                self.assertContains(response, "Select your Smart Q role")
                self.assertNotContains(response, 'id="smartq-react-root"')

    def test_authenticated_workspaces_still_use_react_runtime(self):
        for route_name in [
            "frontend_app",
            "frontend_customer_workspace",
            "frontend_reception_workspace",
            "frontend_counter_workspace",
            "frontend_manager_workspace",
            "frontend_admin_workspace",
            "frontend_history_reporting_workspace",
            "frontend_customer_recovery_workspace",
        ]:
            with self.subTest(route=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'id="smartq-react-root"')
                self.assertContains(response, "/static/react/app.js")
                self.assertContains(response, "/static/react/app.css")

    def test_every_workspace_gets_one_explicit_logout_control(self):
        components = self.repo_text("frontend/src/components.tsx")

        self.assertIn("async function signOut()", components)
        self.assertIn("await logout();", components)
        self.assertIn('className="button button--quiet workspace-logout"', components)
        self.assertIn(">Log out</button>", components)
        self.assertNotIn(">Sign out</button>", components)

    def test_workspace_header_does_not_render_role_notes(self):
        components = self.repo_text("frontend/src/components.tsx")

        self.assertIn("subtitle?: string", components)
        self.assertNotIn("<p>{subtitle}</p>", components)
        self.assertNotIn("subtitle ? <p>", components)
        self.assertNotIn("dialog-intro", components)

    def test_workspace_scale_is_compact_and_bounded(self):
        polish = self.repo_text("frontend/src/polish.css")

        self.assertIn("max-width: 1280px", polish)
        self.assertIn("grid-template-columns: 220px minmax(0, 1fr)", polish)
        self.assertIn("min-height: 420px", polish)
        self.assertIn("font-size: 64px", polish)
        self.assertIn(".workspace-header-actions", polish)
        self.assertIn(".workspace-logout", polish)

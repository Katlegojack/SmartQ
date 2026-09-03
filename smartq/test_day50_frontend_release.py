import re
from pathlib import Path

from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse


class Day50FrontendReleaseAuditTests(TestCase):
    """Release-level integration checks across the complete Smart Q frontend."""

    FRONTEND_ROUTES = (
        "frontend_home",
        "frontend_login",
        "frontend_register",
        "frontend_app",
        "frontend_customer_workspace",
        "frontend_reception_workspace",
        "frontend_counter_workspace",
        "frontend_manager_workspace",
        "frontend_admin_workspace",
        "frontend_history_reporting_workspace",
        "frontend_customer_recovery_workspace",
    )

    PRIMARY_ROLE_WORKSPACES = {
        "frontend_customer_workspace": "customer",
        "frontend_reception_workspace": "receptionist",
        "frontend_counter_workspace": "counter_staff",
        "frontend_manager_workspace": "branch_manager",
        "frontend_admin_workspace": "system_admin",
    }

    WORKSPACE_CSS = (
        "css/customer-dashboard.css",
        "css/reception-workspace.css",
        "css/counter-workspace.css",
        "css/manager-workspace.css",
        "css/admin-workspace.css",
        "css/day49-workflows.css",
    )

    def static_text(self, path):
        resolved = finders.find(path)
        self.assertIsNotNone(resolved, f"Missing static asset: {path}")
        return Path(resolved).read_text(encoding="utf-8")

    def test_all_frontend_entry_routes_render_with_viewport_contract(self):
        for route_name in self.FRONTEND_ROUTES:
            with self.subTest(route=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(
                    response,
                    'name="viewport" content="width=device-width, initial-scale=1"',
                )

    def test_authenticated_workspaces_keep_skip_link_and_main_target(self):
        routes = (
            "frontend_app",
            *self.PRIMARY_ROLE_WORKSPACES.keys(),
            "frontend_history_reporting_workspace",
            "frontend_customer_recovery_workspace",
        )
        for route_name in routes:
            with self.subTest(route=route_name):
                response = self.client.get(reverse(route_name))
                self.assertContains(response, 'class="skip-link"')
                self.assertContains(response, 'id="workspace-main"')

    def test_primary_role_workspaces_share_security_and_logout_shell(self):
        for route_name, role in self.PRIMARY_ROLE_WORKSPACES.items():
            with self.subTest(route=route_name, role=role):
                response = self.client.get(reverse(route_name))
                self.assertContains(response, "data-app-shell")
                self.assertContains(response, f'data-expected-role="{role}"')
                self.assertContains(response, "data-logout")
                self.assertContains(response, "data-security-form")
                self.assertContains(response, "data-security-message")

    def test_shared_accessibility_and_mobile_shell_rules_are_present(self):
        design_system = self.static_text("css/smartq.css")
        shell_css = self.static_text("css/auth-shell.css")

        self.assertIn(":focus-visible", design_system)
        self.assertIn("@media (prefers-reduced-motion: reduce)", design_system)
        self.assertIn(".skip-link:focus", design_system)
        self.assertRegex(shell_css, r"@media\s*\(max-width:\s*760px\)")
        self.assertIn(".app-layout {\n        display: block;", shell_css)
        self.assertIn(".sidebar {\n        position: static;", shell_css)

    def test_every_workspace_stylesheet_has_a_phone_breakpoint(self):
        phone_breakpoint = re.compile(r"@media\s*\(max-width\s*:\s*760px\)")
        compact_phone_breakpoint = re.compile(r"@media\s*\(max-width\s*:\s*760px\)", re.I)
        for path in self.WORKSPACE_CSS:
            with self.subTest(path=path):
                css = self.static_text(path)
                normalized = css.replace("@media(max-width:760px)", "@media (max-width: 760px)")
                self.assertTrue(
                    phone_breakpoint.search(normalized)
                    or compact_phone_breakpoint.search(normalized),
                    f"{path} must define a <=760px release breakpoint",
                )

    def test_role_route_registry_matches_dedicated_workspace_urls(self):
        session_js = self.static_text("js/auth/session.js")
        expected = {
            'customer: "/app/customer/"',
            'receptionist: "/app/reception/"',
            'counter_staff: "/app/counter/"',
            'branch_manager: "/app/manager/"',
            'system_admin: "/app/admin/"',
        }
        for route in expected:
            self.assertIn(route, session_js)

    def test_account_restore_is_shared_across_page_modules(self):
        session_js = self.static_text("js/auth/session.js")
        self.assertIn("let currentAccountPromise = null", session_js)
        self.assertIn("if (refresh || !currentAccountPromise)", session_js)
        self.assertIn("return currentAccountPromise", session_js)
        self.assertIn("clearCurrentAccountCache()", session_js)

    def test_customer_dashboard_release_navigation_and_security_contract(self):
        response = self.client.get(reverse("frontend_customer_workspace"))
        self.assertContains(response, "data-customer-dashboard")
        self.assertContains(response, "data-app-shell")
        self.assertContains(response, 'href="#security"')
        self.assertContains(response, "data-shell-error")

        app_shell_js = self.static_text("js/pages/app-shell.js")
        recovery_function = app_shell_js.split(
            "function ensureCustomerRecoveryNavigation()", 1
        )[1].split("function renderWorkspaceCopy", 1)[0]
        self.assertIn("insertBeforeDivider(nav, link)", recovery_function)
        self.assertIn("customerDashboardOwnsLogout", app_shell_js)

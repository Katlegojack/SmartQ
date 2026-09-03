import json
import re
from datetime import date, time
from pathlib import Path

from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from branches.models import Branch


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
        phone_breakpoint = re.compile(r"@media\s*\(max-width\s*:\s*760px\)", re.I)
        for path in self.WORKSPACE_CSS:
            with self.subTest(path=path):
                css = self.static_text(path)
                normalized = css.replace("@media(max-width:760px)", "@media (max-width: 760px)")
                self.assertRegex(
                    normalized,
                    phone_breakpoint,
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

    def test_login_return_routes_are_role_allowlisted(self):
        session_js = self.static_text("js/auth/session.js")
        login_js = self.static_text("js/pages/login.js")

        self.assertIn(
            'customer: Object.freeze(["/app/customer/", "/app/recovery/"])',
            session_js,
        )
        self.assertIn(
            'branch_manager: Object.freeze(["/app/manager/", "/app/history/"])',
            session_js,
        )
        self.assertIn(
            'system_admin: Object.freeze(["/app/admin/", "/app/history/"])',
            session_js,
        )
        self.assertIn("export function safeNextRoute", session_js)
        self.assertIn('normalized.startsWith("//")', session_js)
        self.assertIn("safeNextRoute", login_js)
        self.assertIn('new URLSearchParams(window.location.search).get("next")', login_js)
        self.assertIn("window.location.replace(safeRoute)", login_js)
        self.assertNotIn("window.location.replace(requested)", login_js)

    def test_mid_session_expiry_uses_shared_login_return_path(self):
        api_client = self.static_text("js/api/client.js")
        app_shell = self.static_text("js/pages/app-shell.js")

        self.assertIn(
            'SESSION_EXPIRED_DETAIL = "Authentication credentials were not provided."',
            api_client,
        )
        self.assertIn('new CustomEvent("smartq:session-expired")', api_client)
        self.assertIn(
            'window.addEventListener("smartq:session-expired", redirectExpiredSession)',
            app_shell,
        )
        self.assertIn("sessionRedirecting", app_shell)
        self.assertIn('window.location.replace(`/login/?next=${next}`)', app_shell)

    def test_router_shell_has_no_stale_frontend_roadmap_placeholder_copy(self):
        response = self.client.get(reverse("frontend_app"))
        self.assertContains(response, "Workspace router")
        self.assertContains(response, "Backend-owned access")
        self.assertNotContains(response, "continue Day 43")
        self.assertNotContains(response, "continue Day 45")
        self.assertNotContains(response, "continue Day 46")
        self.assertNotContains(response, "continue Day 47")
        self.assertNotContains(response, "continue Day 48")

    def test_customer_dashboard_release_navigation_and_security_contract(self):
        response = self.client.get(reverse("frontend_customer_workspace"))
        self.assertContains(response, "data-customer-dashboard")
        self.assertContains(response, "data-app-shell")
        self.assertContains(response, 'href="#security"')
        self.assertContains(response, "data-shell-error")

        app_shell_js = self.static_text("js/pages/app-shell.js")
        recovery_function = app_shell_js.split(
            "function ensureCustomerRecoveryNavigation()", 1
        )[1].split("function setSecurityMessage", 1)[0]
        self.assertIn("insertBeforeDivider(nav, link)", recovery_function)
        self.assertIn("customerDashboardOwnsLogout", app_shell_js)

    def test_admin_self_role_change_refreshes_identity_before_leaving_control_plane(self):
        admin_js = self.static_text("js/pages/admin-workspace.js")
        self.assertIn("const editingId = state.staffEditId", admin_js)
        self.assertIn("getCurrentAccount({ refresh: true })", admin_js)
        self.assertIn('refreshedAccount.role !== "system_admin"', admin_js)
        self.assertIn("window.location.replace(routeForRole(refreshedAccount?.role))", admin_js)

    def test_last_active_system_admin_cannot_be_demoted(self):
        branch = Branch.objects.create(
            branch_code="D50",
            name="Day 50 Branch",
            address="50 Release Street",
            city="Pretoria",
            opening_time=time(8, 0),
            closing_time=time(17, 0),
            is_active=True,
        )
        admin = User.objects.create_user(username="day50_admin", password="pw")
        Profile.objects.create(
            user=admin,
            date_of_birth=date(1990, 1, 1),
            gender=Profile.OTHER,
            role=Profile.SYSTEM_ADMIN,
        )
        self.client.force_login(admin)

        detail_url = reverse("api_admin_staff_detail", args=[admin.id])
        rejected = self.client.patch(
            detail_url,
            data=json.dumps(
                {"role": Profile.RECEPTIONIST, "branch": branch.id}
            ),
            content_type="application/json",
        )
        self.assertEqual(rejected.status_code, 409)
        admin.profile.refresh_from_db()
        self.assertEqual(admin.profile.role, Profile.SYSTEM_ADMIN)

        second_admin = User.objects.create_user(username="day50_admin_2", password="pw")
        Profile.objects.create(
            user=second_admin,
            date_of_birth=date(1991, 2, 2),
            gender=Profile.OTHER,
            role=Profile.SYSTEM_ADMIN,
        )
        allowed = self.client.patch(
            reverse("api_admin_staff_detail", args=[second_admin.id]),
            data=json.dumps(
                {"role": Profile.RECEPTIONIST, "branch": branch.id}
            ),
            content_type="application/json",
        )
        self.assertEqual(allowed.status_code, 200)
        second_admin.profile.refresh_from_db()
        self.assertEqual(second_admin.profile.role, Profile.RECEPTIONIST)
        self.assertEqual(
            User.objects.filter(
                profile__role=Profile.SYSTEM_ADMIN,
                is_active=True,
            ).count(),
            1,
        )

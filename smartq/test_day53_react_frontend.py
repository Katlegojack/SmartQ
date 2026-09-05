from pathlib import Path

from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse


class Day53ReactFrontendReengineeringTests(TestCase):
    """Protect the React runtime cutover and role-specific product surfaces."""

    ROUTES = {
        "frontend_home": ("home", ""),
        "frontend_login": ("login", ""),
        "frontend_staff_login": ("staff_login", ""),
        "frontend_register": ("register", ""),
        "frontend_app": ("router", ""),
        "frontend_customer_workspace": ("customer", "customer"),
        "frontend_reception_workspace": ("reception", "receptionist"),
        "frontend_counter_workspace": ("counter", "counter_staff"),
        "frontend_manager_workspace": ("manager", "branch_manager"),
        "frontend_admin_workspace": ("admin", "system_admin"),
        "frontend_history_reporting_workspace": ("history", ""),
        "frontend_customer_recovery_workspace": ("recovery", ""),
    }

    def frontend_text(self, path):
        return (Path(__file__).resolve().parents[1] / "frontend" / path).read_text(
            encoding="utf-8"
        )

    def test_existing_frontend_routes_boot_one_react_runtime(self):
        for route_name, (page_kind, role) in self.ROUTES.items():
            with self.subTest(route=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'id="smartq-react-root"')
                self.assertContains(response, "/static/react/app.js")
                self.assertContains(response, "/static/react/app.css")
                self.assertContains(response, f'data-page-kind="{page_kind}"')
                if role:
                    self.assertContains(response, f'data-expected-role="{role}"')

    def test_react_toolchain_is_typescript_vite_router_and_query(self):
        package = self.frontend_text("package.json")
        vite = self.frontend_text("vite.config.ts")
        main = self.frontend_text("src/main.tsx")

        for dependency in [
            '"react"',
            '"react-dom"',
            '"react-router-dom"',
            '"@tanstack/react-query"',
            '"typescript"',
            '"vite"',
            '"@types/node"',
        ]:
            self.assertIn(dependency, package)
        self.assertIn('"build": "tsc -b && vite build"', package)
        self.assertIn('resolve(here, "../static/react")', vite)
        self.assertIn("QueryClientProvider", main)
        self.assertIn("BrowserRouter", main)
        self.assertIn('import "./polish.css"', main)
        self.assertIn('import "./accessibility.css"', main)

    def test_react_build_outputs_are_available_to_django(self):
        self.assertIsNotNone(finders.find("react/app.js"))
        self.assertIsNotNone(finders.find("react/app.css"))

    def test_router_preserves_smartq_public_urls(self):
        app = self.frontend_text("src/App.tsx")
        for route in [
            'path="/"',
            'path="/login/"',
            'path="/staff-login/"',
            'path="/register/"',
            'path="/app/customer/"',
            'path="/app/reception/"',
            'path="/app/counter/"',
            'path="/app/manager/"',
            'path="/app/admin/"',
            'path="/app/history/"',
            'path="/app/recovery/"',
        ]:
            self.assertIn(route, app)

    def test_role_routes_and_account_security_remain_explicit(self):
        auth = self.frontend_text("src/auth.ts")
        components = self.frontend_text("src/components.tsx")

        for contract in [
            'customer: "/app/customer/"',
            'receptionist: "/app/reception/"',
            'counter_staff: "/app/counter/"',
            'branch_manager: "/app/manager/"',
            'system_admin: "/app/admin/"',
        ]:
            self.assertIn(contract, auth)
        self.assertIn("safeNextRoute", auth)
        self.assertIn('customer: ["/app/customer/", "/app/recovery/"]', auth)
        self.assertIn('branch_manager: ["/app/manager/", "/app/history/"]', auth)
        self.assertIn('"/api/v1/accounts/change-password/"', components)
        self.assertIn("New password and confirmation must match.", components)
        self.assertIn("Account security", components)

    def test_customer_surface_uses_live_authoritative_booking_contracts(self):
        source = self.frontend_text("src/pages/CustomerPage.tsx")
        for contract in [
            '"/api/v1/bookings/my/"',
            '"/api/v1/queues/my-current/"',
            '"/api/v1/bookings/walk-ins/"',
            '`/api/v1/bookings/${id}/check-in/`',
            '`/api/v1/bookings/${id}/cancel/`',
            '`/api/v1/bookings/${editingBooking?.id}/reschedule/`',
            "refetchInterval: 5_000",
            "refetchInterval: date === today() ? 15_000 : false",
            "Pregnancy applies to this visit",
            "Reschedule",
        ]:
            self.assertIn(contract, source)
        self.assertIn("!next.is_checked_in ?", source)
        self.assertIn("!item.is_checked_in ?", source)
        self.assertNotIn("Checked in</button>", source)

    def test_reception_counter_and_manager_are_live_role_specific_surfaces(self):
        reception = self.frontend_text("src/pages/ReceptionPage.tsx")
        counter = self.frontend_text("src/pages/CounterPage.tsx")
        manager = self.frontend_text("src/pages/ManagerPage.tsx")

        for contract in [
            '"/api/v1/bookings/reception/today/"',
            '"/api/v1/bookings/reception/walk-ins/"',
            '`/api/v1/bookings/${id}/staff-check-in/`',
            "Today's customers",
            "Add customer",
            "refetchInterval: 5_000",
            "Enter at least 2 characters to search.",
        ]:
            self.assertIn(contract, reception)

        for contract in [
            '"/api/v1/counters/my/"',
            "call-next",
            "complete/",
            "no-show/",
            "Call next customer",
            "Complete service",
            "That counter operation could not be completed.",
        ]:
            self.assertIn(contract, counter)

        for contract in [
            "/api/v1/dashboard/branches/",
            "/counter-staff/",
            "Live floor",
            "Services today",
            "Counter operation updated.",
        ]:
            self.assertIn(contract, manager)

    def test_admin_react_console_has_real_crud_and_operating_hours(self):
        source = self.frontend_text("src/pages/AdminPage.tsx")
        for contract in [
            '"/api/v1/accounts/admin/staff/"',
            '"/api/v1/branches/admin/"',
            '"/api/v1/services/admin/"',
            '"/api/v1/services/admin/branch-services/"',
            "opening_time",
            "closing_time",
            "Closing time must be later than opening time.",
            "Create branch",
            "Update branch",
            "Create service",
            "Update service",
            "Create mapping",
            "Update mapping",
            "Create staff account",
            "Update staff",
        ]:
            self.assertIn(contract, source)
        self.assertIn('method: editingBranch ? "PATCH" : "POST"', source)
        self.assertIn('method: editingService ? "PATCH" : "POST"', source)
        self.assertIn('path: `/api/v1/services/admin/branch-services/${editingMapping.id}/`', source)
        self.assertIn('path: `/api/v1/accounts/admin/staff/${editingStaff.id}/`', source)
        self.assertIn('person.id === account.id', source)

    def test_history_and_customer_recovery_are_reimplemented_in_react(self):
        history = self.frontend_text("src/pages/HistoryPage.tsx")
        recovery = self.frontend_text("src/pages/RecoveryPage.tsx")
        for contract in [
            "/reports/operational/",
            "/events/",
            "/api/v1/rescheduling/branches/",
            "/api/v1/rescheduling/pauses/",
        ]:
            self.assertIn(contract, history)
        self.assertIn('"/api/v1/rescheduling/recommendations/my/"', recovery)
        self.assertIn("/api/v1/rescheduling/options/", recovery)

    def test_design_system_is_custom_responsive_and_accessible(self):
        styles = self.frontend_text("src/styles.css")
        workspaces = self.frontend_text("src/workspaces.css")
        polish = self.frontend_text("src/polish.css")
        accessibility = self.frontend_text("src/accessibility.css")

        for selector in [".hero", ".priority-panel", ".reception-grid", ".workspace-shell"]:
            self.assertIn(selector, styles)
        for selector in [
            ".counter-console",
            ".manager-metrics",
            ".admin-tabs",
            ".history-grid",
            ".recovery-card",
        ]:
            self.assertIn(selector, workspaces)
        self.assertIn(".dialog-backdrop", polish)
        self.assertIn("@media(max-width:760px)", styles)
        self.assertIn(":focus-visible", accessibility)
        self.assertIn("@media (prefers-reduced-motion: reduce)", accessibility)

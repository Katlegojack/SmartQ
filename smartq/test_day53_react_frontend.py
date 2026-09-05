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

    def test_existing_frontend_routes_now_boot_one_react_runtime(self):
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
        ]:
            self.assertIn(dependency, package)
        self.assertIn('"build": "tsc -b && vite build"', package)
        self.assertIn('outDir: resolve(__dirname, "../static/react")', vite)
        self.assertIn("QueryClientProvider", main)
        self.assertIn("BrowserRouter", main)

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

    def test_role_routes_remain_explicit(self):
        auth = self.frontend_text("src/auth.ts")
        for contract in [
            'customer: "/app/customer/"',
            'receptionist: "/app/reception/"',
            'counter_staff: "/app/counter/"',
            'branch_manager: "/app/manager/"',
            'system_admin: "/app/admin/"',
        ]:
            self.assertIn(contract, auth)
        self.assertIn("safeNextRoute", auth)

    def test_customer_surface_uses_authoritative_booking_and_queue_contracts(self):
        source = self.frontend_text("src/pages/CustomerPage.tsx")
        for endpoint in [
            '"/api/v1/bookings/my/"',
            '"/api/v1/queues/my-current/"',
            '"/api/v1/bookings/walk-ins/"',
            '`/api/v1/bookings/${bookingId}/check-in/`',
            '`/api/v1/bookings/${bookingId}/cancel/`',
        ]:
            self.assertIn(endpoint, source)
        self.assertIn("refetchInterval: 8_000", source)
        self.assertIn("booking.is_checked_in ? \"Checked in\" : \"Check in\"", source)
        self.assertIn("That appointment time is no longer available", source)

    def test_reception_counter_and_manager_are_role_specific_operational_surfaces(self):
        reception = self.frontend_text("src/pages/ReceptionPage.tsx")
        counter = self.frontend_text("src/pages/CounterPage.tsx")
        manager = self.frontend_text("src/pages/ManagerPage.tsx")

        self.assertIn('"/api/v1/bookings/reception/today/"', reception)
        self.assertIn("Today's customers", reception)
        self.assertIn("Add walk-in", reception)

        self.assertIn('"/api/v1/counters/my/"', counter)
        self.assertIn("Call next", counter)
        self.assertIn("Complete service", counter)

        self.assertIn("/api/v1/dashboard/branches/", manager)
        self.assertIn("Queue pressure", manager)
        self.assertIn("Counter operations", manager)
        self.assertNotIn('to: "/app/history/", label: "History"', reception)

    def test_admin_react_console_uses_real_create_update_and_operating_hours_apis(self):
        source = self.frontend_text("src/pages/AdminPage.tsx")
        for contract in [
            '"/api/v1/accounts/admin/staff/"',
            '"/api/v1/branches/admin/"',
            '"/api/v1/services/admin/"',
            '"/api/v1/services/admin/branch-services/"',
            "opening_time",
            "closing_time",
            "Closing time must be later than opening time.",
        ]:
            self.assertIn(contract, source)
        self.assertIn("Create branch", source)
        self.assertIn("Update branch", source)
        self.assertIn("Create service", source)
        self.assertIn("Update service", source)

    def test_design_system_is_custom_role_specific_and_responsive(self):
        css = self.frontend_text("src/styles.css")
        for selector in [
            ".landing",
            ".customer-home",
            ".workspace-shell",
            ".service-console",
            ".manager-scoreboard",
            ".admin-console",
        ]:
            self.assertIn(selector, css)
        self.assertIn("@media (max-width: 760px)", css)
        self.assertIn(":focus-visible", css)
        self.assertIn("@media (prefers-reduced-motion: reduce)", css)

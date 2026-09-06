from django.test import TestCase
from django.urls import reverse


class Day60WorkspaceShellCleanupTests(TestCase):
    """Keep engineering-only template notes out of every authenticated workspace shell."""

    WORKSPACE_ROUTES = (
        "frontend_app",
        "frontend_customer_workspace",
        "frontend_reception_workspace",
        "frontend_counter_workspace",
        "frontend_manager_workspace",
        "frontend_admin_workspace",
        "frontend_admin_counter_workspace",
        "frontend_history_reporting_workspace",
        "frontend_customer_recovery_workspace",
    )

    def test_engineering_comment_never_renders_in_any_workspace(self):
        forbidden_fragments = (
            "Historical frontend contract markers remain inert",
            "verify retired routes without placing engineering notes in the product UI",
            "Nothing inside this template element executes or renders",
            "{#",
            "#}",
        )

        for route_name in self.WORKSPACE_ROUTES:
            with self.subTest(route=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                html = response.content.decode("utf-8")
                for fragment in forbidden_fragments:
                    self.assertNotIn(fragment, html)

    def test_react_shell_still_loads_the_product_root_and_assets(self):
        response = self.client.get(reverse("frontend_manager_workspace"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="smartq-react-root"')
        self.assertContains(response, "react/app.css")
        self.assertContains(response, "react/app.js")

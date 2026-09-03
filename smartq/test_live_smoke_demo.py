import json
import os
import subprocess
import sys
from io import StringIO
from pathlib import Path

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from accounts.models import Profile
from branches.models import Branch
from counters.models import Counter
from services.models import BranchService, Service


class LiveSmokeDemoBootstrapTests(TestCase):
    def test_bootstrap_demo_creates_complete_role_and_operational_setup(self):
        output = StringIO()
        call_command("bootstrap_demo", stdout=output)

        self.assertEqual(Branch.objects.filter(is_active=True).count(), 2)
        self.assertEqual(Service.objects.filter(is_active=True).count(), 3)
        self.assertEqual(BranchService.objects.filter(is_active=True).count(), 6)
        self.assertEqual(Counter.objects.count(), 5)

        expected_roles = {
            "customer_demo": Profile.CUSTOMER,
            "reception_demo": Profile.RECEPTIONIST,
            "counter_demo": Profile.COUNTER_STAFF,
            "manager_demo": Profile.BRANCH_MANAGER,
            "admin_demo": Profile.SYSTEM_ADMIN,
        }
        for username, role in expected_roles.items():
            with self.subTest(username=username):
                user = User.objects.select_related("profile").get(username=username)
                self.assertTrue(user.is_active)
                self.assertEqual(user.profile.role, role)
                self.assertIsNotNone(
                    authenticate(username=username, password="SmartQDemo2026!")
                )

        self.assertIsNone(User.objects.get(username="customer_demo").profile.branch_id)
        self.assertIsNone(User.objects.get(username="admin_demo").profile.branch_id)
        self.assertIsNotNone(User.objects.get(username="reception_demo").profile.branch_id)
        self.assertIsNotNone(User.objects.get(username="counter_demo").profile.branch_id)
        self.assertIsNotNone(User.objects.get(username="manager_demo").profile.branch_id)

        assigned = Counter.objects.get(
            branch__branch_code="PTA01",
            counter_number="1",
        )
        self.assertEqual(assigned.assigned_staff.username, "counter_demo")
        self.assertIn("Smart Q demo environment is ready", output.getvalue())

    def test_bootstrap_demo_is_idempotent(self):
        call_command("bootstrap_demo", stdout=StringIO())
        call_command("bootstrap_demo", stdout=StringIO())

        self.assertEqual(Branch.objects.count(), 2)
        self.assertEqual(Service.objects.count(), 3)
        self.assertEqual(BranchService.objects.count(), 6)
        self.assertEqual(Counter.objects.count(), 5)
        self.assertEqual(
            User.objects.filter(username__in=[
                "customer_demo",
                "reception_demo",
                "counter_demo",
                "manager_demo",
                "admin_demo",
            ]).count(),
            5,
        )

    @override_settings(IS_PRODUCTION=True)
    def test_bootstrap_demo_refuses_to_run_in_production(self):
        with self.assertRaises(CommandError):
            call_command("bootstrap_demo", stdout=StringIO())

    def test_codespaces_development_origin_is_trusted_automatically(self):
        env = os.environ.copy()
        env.update(
            {
                "SMARTQ_ENV": "development",
                "CODESPACE_NAME": "smartq-demo-space",
                "GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN": "app.github.dev",
                "SMARTQ_DEV_PORT": "8000",
            }
        )
        env.pop("ALLOWED_HOSTS", None)
        env.pop("CSRF_TRUSTED_ORIGINS", None)

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import json; "
                    "from smartq import settings; "
                    "print(json.dumps({"
                    "'hosts': settings.ALLOWED_HOSTS, "
                    "'csrf': settings.CSRF_TRUSTED_ORIGINS"
                    "}))"
                ),
            ],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        payload = json.loads(result.stdout.strip())
        host = "smartq-demo-space-8000.app.github.dev"
        self.assertIn(host, payload["hosts"])
        self.assertIn(f"https://{host}", payload["csrf"])

    def test_customer_booking_ui_does_not_expose_engineering_rule_copy(self):
        resolved = finders.find("js/pages/customer-dashboard.js")
        self.assertIsNotNone(resolved)
        source = Path(resolved).read_text(encoding="utf-8")

        self.assertNotIn("backend-generated availability", source)
        self.assertNotIn("Capacity is revalidated", source)
        self.assertNotIn("Slot duration follows that backend service time", source)
        self.assertIn("No branches are configured yet", source)
        self.assertIn("No times available. Try another date.", source)

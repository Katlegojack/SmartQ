from datetime import date
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from accounts.models import Profile
from branches.models import Branch
from django.contrib.auth.models import User


class Day61BusyDayReadinessTests(TestCase):
    target_date = date(2026, 9, 7)

    def setUp(self):
        call_command(
            "seed_busy_day",
            target_date=self.target_date.isoformat(),
            customers=80,
            verbosity=0,
        )

    def test_preflight_reports_ready_for_seeded_day(self):
        output = StringIO()
        call_command(
            "verify_busy_day",
            target_date=self.target_date.isoformat(),
            customers=80,
            stdout=output,
        )
        rendered = output.getvalue()
        self.assertIn("Customers: 80 | General: 72 | Priority: 8", rendered)
        self.assertIn("READY:", rendered)

    def test_training_manager_is_branch_scoped_and_passwordless_by_default(self):
        manager = User.objects.select_related("profile").get(username="ml_manager")
        branch = Branch.objects.get(branch_code="ML01")
        self.assertEqual(manager.profile.role, Profile.BRANCH_MANAGER)
        self.assertEqual(manager.profile.branch_id, branch.id)
        self.assertFalse(manager.has_usable_password())

    def test_busy_day_source_does_not_commit_training_password(self):
        source = Path("queues/busy_day.py").read_text(encoding="utf-8")
        self.assertIn("SMARTQ_TRAINING_MANAGER_PASSWORD", source)
        self.assertNotIn("SmartQTraining2026!", source)

    @override_settings(IS_PRODUCTION=True)
    def test_seed_verify_and_runner_are_blocked_in_production(self):
        with self.assertRaises(CommandError):
            call_command(
                "seed_busy_day",
                target_date=self.target_date.isoformat(),
                customers=80,
            )
        with self.assertRaises(CommandError):
            call_command(
                "verify_busy_day",
                target_date=self.target_date.isoformat(),
                customers=80,
            )
        with self.assertRaises(CommandError):
            call_command("run_busy_day", target_date=self.target_date.isoformat())

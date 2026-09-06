from datetime import date, datetime, time, timedelta
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Profile
from bookings.services import create_customer_walk_in
from branches.models import Branch
from counters.models import Counter
from queues.forecasting import FORECAST_EXPORT_FIELDS, observation_to_training_row
from queues.models import QueueForecastObservation, QueueTicket
from queues.services import call_next_ticket, complete_current_ticket
from services.models import Service


class Day59ForecastingObservationTests(TestCase):
    """Protect the PII-minimised observation pipeline before any ML model is introduced."""

    PASSWORD = "SafePassword123!"

    def make_user(self, username, role, branch=None):
        user = User.objects.create_user(username=username, password=self.PASSWORD)
        Profile.objects.create(
            user=user,
            date_of_birth=date(1990, 1, 1),
            gender=Profile.OTHER,
            role=role,
            branch=branch,
        )
        return user

    def setUp(self):
        self.day = timezone.localdate()
        self.branch = Branch.objects.create(
            branch_code="D59BARBER",
            name="Day 59 Barber Shop",
            address="59 Forecast Street",
            city="Pretoria",
            opening_time=time(8, 0),
            closing_time=time(18, 0),
            is_active=True,
        )
        self.other_branch = Branch.objects.create(
            branch_code="D59OTHER",
            name="Other Branch",
            address="1 Other Street",
            city="Pretoria",
            opening_time=time(8, 0),
            closing_time=time(18, 0),
            is_active=True,
        )
        self.service = Service.objects.create(
            service_code="CUT59",
            name="Barber service",
            description="Twenty minute Day 59 reference service",
            average_service_time=20,
            is_active=True,
        )
        self.counter = Counter.objects.create(
            branch=self.branch,
            counter_number="1",
            queue_type=QueueTicket.GENERAL,
            status=Counter.OPEN,
        )
        self.first_customer = self.make_user("day59_first", Profile.CUSTOMER)
        self.second_customer = self.make_user("day59_second", Profile.CUSTOMER)
        self.manager = self.make_user("day59_manager", Profile.BRANCH_MANAGER, self.branch)
        self.other_manager = self.make_user(
            "day59_other_manager",
            Profile.BRANCH_MANAGER,
            self.other_branch,
        )
        self.admin = self.make_user("day59_admin", Profile.SYSTEM_ADMIN)

        tz = timezone.get_current_timezone()
        self.started_at = timezone.make_aware(
            datetime.combine(self.day, time(9, 0)),
            tz,
        )

    def create_walk_in_at(self, user, moment):
        with patch("bookings.services.timezone.now", return_value=moment):
            booking, error = create_customer_walk_in(
                user=user,
                branch=self.branch,
                service=self.service,
                actor=user,
            )
        self.assertIsNone(error)
        return booking

    def run_two_customer_early_finish_journey(self):
        first_booking = self.create_walk_in_at(self.first_customer, self.started_at)
        with patch("queues.services.timezone.now", return_value=self.started_at):
            first_called = call_next_ticket(self.counter, booking_date=self.day)
        self.assertEqual(first_called.id, first_booking.queueticket.id)

        second_check_in = self.started_at + timedelta(minutes=5)
        second_booking = self.create_walk_in_at(self.second_customer, second_check_in)

        first_completed_at = self.started_at + timedelta(minutes=15)
        with patch("queues.services.timezone.now", return_value=first_completed_at):
            complete_current_ticket(self.counter)
        with patch("queues.services.timezone.now", return_value=first_completed_at):
            second_called = call_next_ticket(self.counter, booking_date=self.day)
        self.assertEqual(second_called.id, second_booking.queueticket.id)

        second_completed_at = self.started_at + timedelta(minutes=28)
        with patch("queues.services.timezone.now", return_value=second_completed_at):
            complete_current_ticket(self.counter)

        return first_booking, second_booking

    def test_queue_entry_snapshot_and_actual_wait_residual_are_preserved(self):
        _, second_booking = self.run_two_customer_early_finish_journey()

        observation = QueueForecastObservation.objects.get(
            ticket=second_booking.queueticket
        )
        self.assertEqual(observation.people_ahead, 1)
        self.assertEqual(observation.open_counter_count, 1)
        self.assertEqual(observation.serving_count, 1)
        self.assertEqual(observation.baseline_estimated_wait_seconds, 15 * 60)

        # A001 finished at 09:15 instead of 09:20, so A002 waited 10 minutes
        # rather than the 15-minute queue-entry estimate. The saved five minutes
        # become a negative prediction residual instead of being discarded.
        self.assertEqual(observation.actual_wait_seconds, 10 * 60)
        self.assertEqual(observation.wait_variance_seconds, -5 * 60)

        # A002 then completed its own 20-minute target in 13 minutes.
        self.assertEqual(observation.service_target_seconds, 20 * 60)
        self.assertEqual(observation.actual_service_seconds, 13 * 60)
        self.assertEqual(observation.service_variance_seconds, -7 * 60)

    def test_training_row_and_storage_exclude_customer_pii(self):
        _, second_booking = self.run_two_customer_early_finish_journey()
        observation = QueueForecastObservation.objects.get(
            ticket=second_booking.queueticket
        )
        row = observation_to_training_row(observation)

        self.assertEqual(list(row.keys()), FORECAST_EXPORT_FIELDS)
        self.assertEqual(row["branch_id"], self.branch.id)
        self.assertEqual(row["service_id"], self.service.id)
        self.assertEqual(row["people_ahead"], 1)

        forbidden = {
            "customer_name",
            "username",
            "email",
            "phone_number",
            "date_of_birth",
            "gender",
            "disability_status",
            "is_pregnant",
        }
        self.assertTrue(forbidden.isdisjoint(row.keys()))
        model_fields = {field.name for field in QueueForecastObservation._meta.get_fields()}
        self.assertTrue(forbidden.isdisjoint(model_fields))

    def test_forecasting_summary_reports_baseline_error_without_claiming_ml(self):
        self.run_two_customer_early_finish_journey()
        self.client.force_login(self.manager)

        url = reverse("api_branch_forecasting_summary", args=[self.branch.id])
        response = self.client.get(
            f"{url}?start_date={self.day.isoformat()}&end_date={self.day.isoformat()}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["model_status"], "data_collection")
        self.assertFalse(response.json()["machine_learning_enabled"])
        self.assertEqual(response.json()["observations"], 2)
        self.assertEqual(response.json()["wait_labels"], 2)
        self.assertEqual(response.json()["service_labels"], 2)
        self.assertEqual(response.json()["baseline_wait_mae_minutes"], 2.5)
        self.assertEqual(response.json()["baseline_wait_bias_minutes"], -2.5)
        self.assertEqual(response.json()["service_target_mae_minutes"], 6.0)
        self.assertEqual(response.json()["service_target_bias_minutes"], -6.0)

    def test_forecasting_summary_is_branch_scoped(self):
        self.client.force_login(self.other_manager)
        url = reverse("api_branch_forecasting_summary", args=[self.branch.id])
        denied = self.client.get(url)
        self.assertEqual(denied.status_code, 403)

        self.client.force_login(self.admin)
        allowed = self.client.get(url)
        self.assertEqual(allowed.status_code, 200)

    def test_export_command_writes_only_approved_dataset_columns(self):
        self.run_two_customer_early_finish_journey()
        stdout = StringIO()
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "forecast.csv"
            call_command(
                "export_forecasting_dataset",
                branch_id=self.branch.id,
                start_date=self.day.isoformat(),
                end_date=self.day.isoformat(),
                output=str(output),
                stdout=stdout,
            )
            lines = output.read_text(encoding="utf-8").splitlines()

        self.assertEqual(lines[0].split(","), FORECAST_EXPORT_FIELDS)
        self.assertEqual(len(lines), 3)
        header = lines[0].lower()
        for forbidden in [
            "customer_name",
            "email",
            "phone",
            "date_of_birth",
            "gender",
            "disability",
            "pregnant",
        ]:
            self.assertNotIn(forbidden, header)

    def test_forecasting_pipeline_is_event_driven_for_all_queue_entry_paths(self):
        apps = Path(__file__).resolve().parents[1] / "queues" / "apps.py"
        signals = Path(__file__).resolve().parents[1] / "queues" / "signals.py"
        forecasting = Path(__file__).resolve().parents[1] / "queues" / "forecasting.py"

        self.assertIn("from . import signals", apps.read_text(encoding="utf-8"))
        signal_source = signals.read_text(encoding="utf-8")
        self.assertIn("QueueEvent.CHECKED_IN", signal_source)
        self.assertIn("QueueEvent.CALLED", signal_source)
        self.assertIn("QueueEvent.COMPLETED", signal_source)
        forecast_source = forecasting.read_text(encoding="utf-8")
        self.assertIn("baseline_estimated_wait_seconds", forecast_source)
        self.assertIn("actual_wait_seconds", forecast_source)
        self.assertIn("wait_variance_seconds", forecast_source)

    def test_manager_history_ui_exposes_collection_quality_without_claiming_ml(self):
        root = Path(__file__).resolve().parents[1]
        history = (root / "frontend" / "src" / "pages" / "HistoryPage.tsx").read_text(
            encoding="utf-8"
        )
        readme = (root / "README.md").read_text(encoding="utf-8")

        self.assertIn("reports/forecasting/", history)
        self.assertIn("Data collection quality", history)
        self.assertIn("Wait baseline MAE", history)
        self.assertIn("Service target MAE", history)
        self.assertIn("No machine-learning model is active yet.", history)
        self.assertIn("machine_learning_enabled = false", readme)
        self.assertIn("export_forecasting_dataset", readme)

from datetime import date, datetime, time, timedelta
from time import perf_counter
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import Profile
from bookings.models import Booking
from branches.models import Branch
from counters.models import Counter
from queues.ml_prediction import (
    REQUIRED_FEATURES,
    build_live_ml_features,
    load_wait_model_bundle,
)
from queues.models import QueueTicket
from queues.services import call_next_ticket
from queues.waiting_time import get_ticket_prediction
from services.models import Service


class SmartQMLIntegrationTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.branch = Branch.objects.create(
            branch_code="PTC1",
            name="Pretoria Central",
            address="ML integration test",
            city="Pretoria",
            opening_time=time(8, 0),
            closing_time=time(18, 0),
            is_active=True,
        )
        self.service = Service.objects.create(
            service_code="IDAPP",
            name="ID Applications",
            description="ML integration test service",
            average_service_time=15,
            is_active=True,
        )
        self.general_counter = Counter.objects.create(
            branch=self.branch,
            counter_number="1",
            queue_type=QueueTicket.GENERAL,
            status=Counter.OPEN,
        )
        self.priority_counter = Counter.objects.create(
            branch=self.branch,
            counter_number="2",
            queue_type=QueueTicket.PRIORITY,
            status=Counter.OPEN,
        )
        self.user = User.objects.create_user(
            username="ml_integration_customer",
            password="SafePassword123!",
        )
        Profile.objects.create(
            user=self.user,
            date_of_birth=date(1995, 1, 1),
            gender=Profile.OTHER,
            role=Profile.CUSTOMER,
        )

        tz = timezone.get_current_timezone()
        self.now = timezone.make_aware(
            datetime.combine(self.today, time(10, 0)),
            tz,
        )
        self.booking = Booking.objects.create(
            user=self.user,
            branch=self.branch,
            service=self.service,
            booking_date=self.today,
            booking_time=time(10, 0),
            source=Booking.ONLINE,
            status=Booking.PENDING,
            checked_in_at=self.now,
        )
        self.ticket = QueueTicket.objects.create(
            booking=self.booking,
            queue_number="A001",
            queue_type=QueueTicket.GENERAL,
            status=QueueTicket.WAITING,
        )

    def test_live_feature_builder_matches_the_22_feature_contract(self):
        features = build_live_ml_features(self.ticket, now=self.now)

        self.assertEqual(set(features), set(REQUIRED_FEATURES))
        self.assertEqual(len(features), 22)
        self.assertEqual(features["branch_code"], "PTC1")
        self.assertEqual(features["service_code"], "IDAPP")
        self.assertEqual(features["booking_source"], "APPOINTMENT")
        self.assertEqual(features["queue_type"], "GENERAL")
        self.assertEqual(features["arrival_offset_minutes"], 0.0)
        self.assertEqual(features["people_ahead"], 0.0)
        self.assertEqual(features["general_waiting"], 0.0)
        self.assertEqual(features["priority_waiting"], 0.0)
        self.assertEqual(features["open_general_counters"], 1.0)
        self.assertEqual(features["open_priority_counters"], 1.0)
        self.assertEqual(features["effective_open_counters"], 1.0)
        self.assertEqual(features["queue_pressure_index"], 0.0)
        self.assertEqual(features["service_target_minutes"], 15.0)
        self.assertTrue(features["is_peak_period"])

    def test_customer_current_queue_api_returns_xgboost_prediction(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("api_my_current_queue_ticket"))

        self.assertEqual(response.status_code, 200)
        prediction = response.json()["prediction"]
        self.assertEqual(prediction["prediction_model"], "xgboost")
        self.assertEqual(prediction["model_status"], "active")
        self.assertTrue(prediction["machine_learning_enabled"])
        self.assertIsNotNone(prediction["ml_predicted_wait_minutes"])
        self.assertGreaterEqual(prediction["estimated_wait_seconds"], 0)

    def test_packaged_xgboost_model_produces_live_prediction(self):
        load_wait_model_bundle.cache_clear()
        prediction = get_ticket_prediction(
            self.ticket,
            now=self.now,
            use_ml=True,
        )

        self.assertEqual(prediction["prediction_model"], "xgboost")
        self.assertEqual(prediction["model_status"], "active")
        self.assertTrue(prediction["machine_learning_enabled"])
        self.assertIsNotNone(prediction["ml_predicted_wait_minutes"])
        self.assertGreaterEqual(prediction["estimated_wait_seconds"], 0)

    def test_cold_and_warm_ml_prediction_are_under_two_seconds(self):
        load_wait_model_bundle.cache_clear()

        cold_started = perf_counter()
        cold_prediction = get_ticket_prediction(
            self.ticket,
            now=self.now,
            use_ml=True,
        )
        cold_elapsed = perf_counter() - cold_started

        warm_started = perf_counter()
        warm_prediction = get_ticket_prediction(
            self.ticket,
            now=self.now,
            use_ml=True,
        )
        warm_elapsed = perf_counter() - warm_started

        print(f"SMARTQ_ML_COLD_PREDICTION_SECONDS={cold_elapsed:.6f}")
        print(f"SMARTQ_ML_WARM_PREDICTION_SECONDS={warm_elapsed:.6f}")

        self.assertEqual(cold_prediction["prediction_model"], "xgboost")
        self.assertEqual(warm_prediction["prediction_model"], "xgboost")
        self.assertLess(cold_elapsed, 2.0)
        self.assertLess(warm_elapsed, 2.0)

    @override_settings(SMARTQ_ML_ENABLED=False)
    def test_disabled_ml_uses_deterministic_fallback_contract(self):
        prediction = get_ticket_prediction(
            self.ticket,
            now=self.now,
            use_ml=True,
        )

        self.assertEqual(prediction["prediction_model"], "deterministic")
        self.assertEqual(prediction["model_status"], "deterministic")
        self.assertFalse(prediction["machine_learning_enabled"])
        self.assertEqual(
            prediction["estimated_wait_seconds"],
            prediction["deterministic_estimated_wait_seconds"],
        )

    def test_out_of_domain_arrival_offset_uses_safe_deterministic_fallback(self):
        self.booking.booking_time = time(10, 30)
        self.booking.save(update_fields=["booking_time"])

        prediction = get_ticket_prediction(
            self.ticket,
            now=self.now,
            use_ml=True,
        )

        self.assertEqual(prediction["prediction_model"], "deterministic")
        self.assertEqual(prediction["model_status"], "fallback")
        self.assertFalse(prediction["machine_learning_enabled"])
        self.assertIn(
            "arrival_offset_minutes=-30 outside [-25, 25]",
            prediction["prediction_fallback_reason"],
        )
        self.assertEqual(
            prediction["estimated_wait_seconds"],
            prediction["deterministic_estimated_wait_seconds"],
        )

    def test_early_checked_in_appointment_cannot_be_called_before_booking_time(self):
        future_time = (self.now + timedelta(minutes=30)).time().replace(tzinfo=None)
        self.booking.booking_time = future_time
        self.booking.save(update_fields=["booking_time"])

        with patch("queues.services.timezone.now", return_value=self.now):
            called = call_next_ticket(self.general_counter, booking_date=self.today)

        self.assertIsNone(called)

        appointment_at = self.now + timedelta(minutes=30)
        with patch("queues.services.timezone.now", return_value=appointment_at):
            called = call_next_ticket(self.general_counter, booking_date=self.today)

        self.assertIsNotNone(called)
        self.assertEqual(called.pk, self.ticket.pk)

from concurrent.futures import ThreadPoolExecutor
from datetime import time, timedelta
from unittest import skipUnless

from django.contrib.auth.models import User
from django.db import connection, connections
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework import serializers

from bookings.models import Booking
from bookings.serializers import BookingCreateSerializer
from branches.models import Branch

from .models import BranchService, Service


@skipUnless(
    connection.vendor == "postgresql",
    "Concurrent capacity verification requires PostgreSQL.",
)
class PostgreSQLSlotCapacityConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.branch = Branch.objects.create(
            branch_code="PTA001",
            name="Pretoria Branch",
            address="Civic Centre",
            city="Pretoria",
            opening_time=time(8, 0),
            closing_time=time(16, 0),
        )
        self.service = Service.objects.create(
            service_code="PASS001",
            name="Passport Service",
            description="Passport processing",
            average_service_time=10,
        )
        BranchService.objects.create(
            branch=self.branch,
            service=self.service,
            max_bookings_per_slot=1,
        )
        self.users = [
            User.objects.create_user(
                username=f"capacity.user.{index}",
                password="Strong-Test-Pass-482!",
            )
            for index in range(2)
        ]
        self.booking_date = timezone.localdate() + timedelta(days=1)

    def attempt_booking(self, user_id):
        thread_connection = connections["default"]
        thread_connection.close()
        try:
            user = User.objects.get(pk=user_id)
            serializer = BookingCreateSerializer(
                data={
                    "branch": self.branch.pk,
                    "service": self.service.pk,
                    "booking_date": self.booking_date.isoformat(),
                    "booking_time": "09:00:00",
                    "is_pregnant": False,
                }
            )
            serializer.is_valid(raise_exception=True)
            try:
                serializer.save(user=user, source=Booking.ONLINE)
                return "created"
            except serializers.ValidationError:
                return "slot_full"
        finally:
            thread_connection.close()

    def test_only_one_concurrent_booking_consumes_last_slot(self):
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(self.attempt_booking, [user.pk for user in self.users]))

        self.assertEqual(results.count("created"), 1)
        self.assertEqual(results.count("slot_full"), 1)
        self.assertEqual(
            Booking.objects.filter(
                branch=self.branch,
                service=self.service,
                booking_date=self.booking_date,
                booking_time=time(9, 0),
            ).count(),
            1,
        )

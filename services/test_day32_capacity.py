from datetime import date, time, timedelta

from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Profile
from bookings.models import Booking
from branches.models import Branch
from .availability import generate_slot_times, get_slot_availability
from .models import BranchService, Service


class BranchServiceAvailabilityTests(APITestCase):
    """Day 32 regression tests for branch-service mapping and slot capacity."""

    def setUp(self):
        self.branch = Branch.objects.create(
            branch_code="PTA01",
            name="Pretoria Branch",
            address="1 Main Street",
            city="Pretoria",
            opening_time=time(8, 0),
            closing_time=time(10, 0),
            is_active=True,
        )
        self.other_branch = Branch.objects.create(
            branch_code="KIM01",
            name="Kimberley Branch",
            address="2 Main Street",
            city="Kimberley",
            opening_time=time(8, 0),
            closing_time=time(10, 0),
            is_active=True,
        )
        self.service = Service.objects.create(
            service_code="ID01",
            name="ID Application",
            description="ID service",
            average_service_time=20,
            is_active=True,
        )
        self.unmapped_service = Service.objects.create(
            service_code="PASS01",
            name="Passport",
            description="Passport service",
            average_service_time=30,
            is_active=True,
        )
        self.mapping = BranchService.objects.create(
            branch=self.branch,
            service=self.service,
            max_bookings_per_slot=2,
        )
        self.booking_date = timezone.localdate() + timedelta(days=2)

        self.user = User.objects.create_user(username="customer", password="pw")
        Profile.objects.create(
            user=self.user,
            date_of_birth=date(1990, 1, 1),
            gender=Profile.OTHER,
            role=Profile.CUSTOMER,
        )

    def test_slot_duration_uses_service_average_service_time(self):
        slots = generate_slot_times(self.branch, self.service, self.booking_date)
        self.assertEqual(
            slots,
            [
                time(8, 0),
                time(8, 20),
                time(8, 40),
                time(9, 0),
                time(9, 20),
                time(9, 40),
            ],
        )

    def test_branch_service_list_returns_only_mapped_services(self):
        response = self.client.get(
            reverse("api_branch_service_list", kwargs={"branch_id": self.branch.id})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["service_id"], self.service.id)
        self.assertEqual(response.data[0]["max_bookings_per_slot"], 2)

    def test_unmapped_service_availability_returns_not_found(self):
        response = self.client.get(
            reverse(
                "api_branch_service_availability",
                kwargs={
                    "branch_id": self.branch.id,
                    "service_id": self.unmapped_service.id,
                },
            ),
            {"date": str(self.booking_date)},
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_availability_reports_remaining_capacity(self):
        Booking.objects.create(
            user=self.user,
            branch=self.branch,
            service=self.service,
            booking_date=self.booking_date,
            booking_time=time(8, 0),
            source=Booking.ONLINE,
            status=Booking.PENDING,
        )

        slots = get_slot_availability(self.branch, self.service, self.booking_date)
        first = next(slot for slot in slots if slot["time"] == time(8, 0))
        self.assertEqual(first["capacity"], 2)
        self.assertEqual(first["booked"], 1)
        self.assertEqual(first["remaining"], 1)
        self.assertTrue(first["is_available"])

    def test_full_slot_is_reported_unavailable(self):
        second_user = User.objects.create_user(username="customer2", password="pw")
        Profile.objects.create(
            user=second_user,
            date_of_birth=date(1991, 1, 1),
            gender=Profile.OTHER,
            role=Profile.CUSTOMER,
        )
        for user in [self.user, second_user]:
            Booking.objects.create(
                user=user,
                branch=self.branch,
                service=self.service,
                booking_date=self.booking_date,
                booking_time=time(8, 0),
                source=Booking.ONLINE,
                status=Booking.PENDING,
            )

        slots = get_slot_availability(self.branch, self.service, self.booking_date)
        first = next(slot for slot in slots if slot["time"] == time(8, 0))
        self.assertEqual(first["remaining"], 0)
        self.assertFalse(first["is_available"])

    def test_cancelled_booking_releases_capacity(self):
        Booking.objects.create(
            user=self.user,
            branch=self.branch,
            service=self.service,
            booking_date=self.booking_date,
            booking_time=time(8, 0),
            source=Booking.ONLINE,
            status=Booking.CANCELLED,
        )

        slots = get_slot_availability(self.branch, self.service, self.booking_date)
        first = next(slot for slot in slots if slot["time"] == time(8, 0))
        self.assertEqual(first["booked"], 0)
        self.assertEqual(first["remaining"], 2)

    def test_walk_in_does_not_consume_future_appointment_capacity(self):
        guest_user = User.objects.create_user(username="legacywalkin", password="pw")
        Profile.objects.create(
            user=guest_user,
            date_of_birth=date(1992, 1, 1),
            gender=Profile.OTHER,
            role=Profile.CUSTOMER,
        )
        Booking.objects.create(
            user=guest_user,
            branch=self.branch,
            service=self.service,
            booking_date=self.booking_date,
            booking_time=time(8, 0),
            source=Booking.WALK_IN,
            status=Booking.PENDING,
        )

        slots = get_slot_availability(self.branch, self.service, self.booking_date)
        first = next(slot for slot in slots if slot["time"] == time(8, 0))
        self.assertEqual(first["booked"], 0)

    def test_availability_api_returns_service_duration_and_capacity(self):
        response = self.client.get(
            reverse(
                "api_branch_service_availability",
                kwargs={"branch_id": self.branch.id, "service_id": self.service.id},
            ),
            {"date": str(self.booking_date)},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["slot_duration_minutes"], 20)
        self.assertEqual(response.data["max_bookings_per_slot"], 2)
        self.assertEqual(len(response.data["slots"]), 6)

from datetime import date, time, timedelta

from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Profile
from bookings.models import Booking
from branches.models import Branch
from queues.models import QueueTicket
from services.models import BranchService, Service


class Day44AppointmentBookingExperienceTests(APITestCase):
    def setUp(self):
        self.branch = Branch.objects.create(
            branch_code="PTA44",
            name="Pretoria Day 44",
            address="44 Main Street",
            city="Pretoria",
            opening_time=time(8, 0),
            closing_time=time(10, 0),
            is_active=True,
        )
        self.service = Service.objects.create(
            service_code="ID44",
            name="ID Application",
            description="Identity document application",
            average_service_time=30,
            is_active=True,
        )
        BranchService.objects.create(
            branch=self.branch,
            service=self.service,
            max_bookings_per_slot=1,
            is_active=True,
        )
        self.customer = User.objects.create_user(
            username="day44customer",
            password="SafePassword123!",
            first_name="Thato",
        )
        Profile.objects.create(
            user=self.customer,
            date_of_birth=date(1995, 5, 10),
            gender=Profile.OTHER,
            role=Profile.CUSTOMER,
        )
        self.booking_date = timezone.localdate() + timedelta(days=1)

    def authenticate(self):
        self.client.force_authenticate(self.customer)

    def first_available_slot(self, booking_date=None):
        response = self.client.get(
            reverse(
                "api_branch_service_availability",
                args=[self.branch.id, self.service.id],
            ),
            {"date": str(booking_date or self.booking_date)},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        slots = [slot for slot in response.data["slots"] if slot["is_available"]]
        self.assertTrue(slots)
        return slots[0]["time"]

    def test_customer_workspace_renders_day44_booking_contract(self):
        response = self.client.get(reverse("frontend_customer_workspace"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Book appointment")
        self.assertContains(response, "data-booking-workflow")
        self.assertContains(response, "data-booking-branch")
        self.assertContains(response, "data-booking-service")
        self.assertContains(response, "data-booking-date")
        self.assertContains(response, "data-slot-grid")
        self.assertContains(response, "Availability is advisory until the final server write")

    def test_day44_customer_assets_remain_discoverable(self):
        self.assertIsNotNone(finders.find("css/customer-dashboard.css"))
        self.assertIsNotNone(finders.find("js/pages/customer-dashboard.js"))

    def test_customer_can_create_booking_from_backend_availability(self):
        self.authenticate()
        slot = self.first_available_slot()

        response = self.client.post(
            reverse("api_booking_create"),
            {
                "branch": self.branch.id,
                "service": self.service.id,
                "booking_date": str(self.booking_date),
                "booking_time": slot,
                "is_pregnant": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        booking = Booking.objects.get(pk=response.data["id"])
        self.assertEqual(booking.user, self.customer)
        self.assertEqual(booking.source, Booking.ONLINE)
        self.assertEqual(booking.branch, self.branch)
        self.assertEqual(booking.service, self.service)
        ticket = booking.queueticket
        self.assertEqual(ticket.status, QueueTicket.SCHEDULED)
        self.assertEqual(ticket.queue_number, "A001")

    def test_reschedule_reuses_backend_availability_and_requires_fresh_check_in(self):
        self.authenticate()
        first_slot = self.first_available_slot()
        created = self.client.post(
            reverse("api_booking_create"),
            {
                "branch": self.branch.id,
                "service": self.service.id,
                "booking_date": str(self.booking_date),
                "booking_time": first_slot,
                "is_pregnant": False,
            },
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        booking = Booking.objects.get(pk=created.data["id"])

        new_date = self.booking_date + timedelta(days=1)
        new_slot = self.first_available_slot(new_date)
        response = self.client.patch(
            reverse("api_booking_reschedule", args=[booking.id]),
            {"booking_date": str(new_date), "booking_time": new_slot},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        booking.refresh_from_db()
        booking.queueticket.refresh_from_db()
        self.assertEqual(booking.booking_date, new_date)
        self.assertIsNone(booking.checked_in_at)
        self.assertEqual(booking.status, Booking.PENDING)
        self.assertEqual(booking.queueticket.status, QueueTicket.SCHEDULED)

    def test_non_female_profile_cannot_submit_pregnancy_priority_directly(self):
        self.authenticate()
        slot = self.first_available_slot()

        response = self.client.post(
            reverse("api_booking_create"),
            {
                "branch": self.branch.id,
                "service": self.service.id,
                "booking_date": str(self.booking_date),
                "booking_time": slot,
                "is_pregnant": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("is_pregnant", response.data)
        self.assertEqual(Booking.objects.count(), 0)

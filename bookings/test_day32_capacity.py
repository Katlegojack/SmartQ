from datetime import date, time, timedelta

from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounts.models import Profile
from branches.models import Branch
from queues.models import QueueTicket
from services.models import BranchService, Service
from .models import Booking


class BookingCapacityEnforcementTests(APITestCase):
    """Prove clients cannot bypass Day 32 branch/service and slot rules."""

    def setUp(self):
        self.branch = Branch.objects.create(
            branch_code="PTA01",
            name="Pretoria Branch",
            address="1 Main Street",
            city="Pretoria",
            opening_time=time(8, 0),
            closing_time=time(12, 0),
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
            max_bookings_per_slot=1,
        )
        self.customer = User.objects.create_user(username="customer", password="pw")
        Profile.objects.create(
            user=self.customer,
            date_of_birth=date(1990, 1, 1),
            gender=Profile.OTHER,
            role=Profile.CUSTOMER,
        )
        self.booking_date = timezone.localdate() + timedelta(days=2)
        self.client = APIClient()
        self.client.force_authenticate(user=self.customer)

    def _payload(self, *, service=None, booking_time="08:00:00"):
        return {
            "branch": self.branch.id,
            "service": (service or self.service).id,
            "booking_date": str(self.booking_date),
            "booking_time": booking_time,
            "is_pregnant": False,
        }

    def test_valid_generated_slot_can_be_booked(self):
        response = self.client.post(
            reverse("api_booking_create"),
            self._payload(),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        booking = Booking.objects.get(pk=response.data["id"])
        self.assertEqual(booking.booking_time, time(8, 0))
        self.assertEqual(booking.queueticket.status, QueueTicket.SCHEDULED)

    def test_service_not_offered_at_branch_is_rejected(self):
        response = self.client.post(
            reverse("api_booking_create"),
            self._payload(service=self.unmapped_service),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Booking.objects.count(), 0)

    def test_arbitrary_non_generated_time_is_rejected(self):
        response = self.client.post(
            reverse("api_booking_create"),
            self._payload(booking_time="08:15:00"),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Booking.objects.count(), 0)

    def test_full_slot_rejects_next_booking(self):
        first = self.client.post(
            reverse("api_booking_create"),
            self._payload(),
            format="json",
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)

        second_user = User.objects.create_user(username="customer2", password="pw")
        Profile.objects.create(
            user=second_user,
            date_of_birth=date(1991, 1, 1),
            gender=Profile.OTHER,
            role=Profile.CUSTOMER,
        )
        self.client.force_authenticate(user=second_user)
        second = self.client.post(
            reverse("api_booking_create"),
            self._payload(),
            format="json",
        )

        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Booking.objects.count(), 1)

    def test_cancelled_booking_releases_slot_for_another_customer(self):
        existing = Booking.objects.create(
            user=self.customer,
            branch=self.branch,
            service=self.service,
            booking_date=self.booking_date,
            booking_time=time(8, 0),
            source=Booking.ONLINE,
            status=Booking.CANCELLED,
        )
        self.assertIsNotNone(existing)

        response = self.client.post(
            reverse("api_booking_create"),
            self._payload(),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_reschedule_to_full_slot_is_rejected(self):
        existing = Booking.objects.create(
            user=self.customer,
            branch=self.branch,
            service=self.service,
            booking_date=self.booking_date,
            booking_time=time(8, 20),
            source=Booking.ONLINE,
            status=Booking.PENDING,
        )
        QueueTicket.objects.create(
            booking=existing,
            queue_number="A001",
            queue_type=QueueTicket.GENERAL,
            status=QueueTicket.SCHEDULED,
        )

        other = User.objects.create_user(username="other", password="pw")
        Profile.objects.create(
            user=other,
            date_of_birth=date(1990, 1, 1),
            gender=Profile.OTHER,
            role=Profile.CUSTOMER,
        )
        Booking.objects.create(
            user=other,
            branch=self.branch,
            service=self.service,
            booking_date=self.booking_date,
            booking_time=time(8, 0),
            source=Booking.ONLINE,
            status=Booking.PENDING,
        )

        response = self.client.patch(
            reverse("api_booking_reschedule", kwargs={"pk": existing.id}),
            {
                "booking_date": str(self.booking_date),
                "booking_time": "08:00:00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        existing.refresh_from_db()
        self.assertEqual(existing.booking_time, time(8, 20))


class GuestWalkInBranchServiceTests(APITestCase):
    """Walk-ins remain immediate, but only for services the branch offers."""

    def setUp(self):
        self.branch = Branch.objects.create(
            branch_code="KIM01",
            name="Kimberley Branch",
            address="1 Main Street",
            city="Kimberley",
            opening_time=time(8, 0),
            closing_time=time(16, 0),
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
        BranchService.objects.create(
            branch=self.branch,
            service=self.service,
            max_bookings_per_slot=2,
        )
        self.receptionist = User.objects.create_user(username="reception", password="pw")
        Profile.objects.create(
            user=self.receptionist,
            date_of_birth=date(1990, 1, 1),
            gender=Profile.OTHER,
            role=Profile.RECEPTIONIST,
            branch=self.branch,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.receptionist)

    def test_guest_walk_in_for_unoffered_service_is_rejected(self):
        response = self.client.post(
            reverse("api_reception_guest_walk_in"),
            {
                "full_name": "Guest Person",
                "date_of_birth": "1990-01-01",
                "gender": Profile.OTHER,
                "service": self.unmapped_service.id,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Booking.objects.count(), 0)

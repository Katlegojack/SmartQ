from datetime import date, time, timedelta

from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Profile
from bookings.models import Booking
from branches.models import Branch
from notifications.models import Notification
from queues.models import QueueDisruptionImpact, QueuePause, QueueTicket
from services.models import BranchService, Service

from .models import RescheduleRecommendation
from .services import create_reschedule_recommendation_for_impact


class Day35CustomerSelectionAPITests(APITestCase):
    """Customer ownership, atomicity and lifecycle tests for disruption rescheduling."""

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
        self.service = Service.objects.create(
            service_code="ID01",
            name="ID Application",
            description="ID service",
            average_service_time=10,
            is_active=True,
        )
        BranchService.objects.create(
            branch=self.branch,
            service=self.service,
            max_bookings_per_slot=2,
        )

        self.customer = self._create_customer("customer")
        self.other_customer = self._create_customer("other")
        self.booking = self._create_booking(self.customer, "A001")
        self.other_booking = self._create_booking(self.other_customer, "A002")
        self.recommendation = self._create_recommendation(self.booking)
        self.other_recommendation = self._create_recommendation(self.other_booking)

    def _create_customer(self, username):
        user = User.objects.create_user(username=username, password="pw")
        Profile.objects.create(
            user=user,
            date_of_birth=date(1995, 1, 1),
            gender=Profile.OTHER,
            role=Profile.CUSTOMER,
        )
        return user

    def _create_booking(self, user, queue_number):
        booking = Booking.objects.create(
            user=user,
            branch=self.branch,
            service=self.service,
            booking_date=timezone.localdate(),
            booking_time=time(9, 0),
            status=Booking.CONFIRMED,
            source=Booking.ONLINE,
            checked_in_at=timezone.now() - timedelta(minutes=30),
        )
        QueueTicket.objects.create(
            booking=booking,
            queue_number=queue_number,
            queue_type=QueueTicket.GENERAL,
            status=QueueTicket.WAITING,
        )
        return booking

    def _create_recommendation(self, booking):
        pause = QueuePause.objects.create(
            branch=self.branch,
            service=self.service,
            booking_date=booking.booking_date,
            started_at=timezone.now() - timedelta(minutes=20),
            ended_at=timezone.now(),
            reason="Network outage",
            is_active=False,
        )
        impact = QueueDisruptionImpact.objects.create(
            queue_pause=pause,
            ticket=booking.queueticket,
            impact_type=QueueDisruptionImpact.RESCHEDULE_RISK,
            message="You may need to be rescheduled due to a service disruption.",
        )
        result = create_reschedule_recommendation_for_impact(impact)
        self.assertIsNotNone(result["recommendation"])
        return result["recommendation"]

    def test_customer_lists_only_own_recommendations(self):
        self.client.force_authenticate(user=self.customer)
        response = self.client.get(reverse("api_my_reschedule_recommendations"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.recommendation.id)
        self.assertEqual(response.data[0]["booking_id"], self.booking.id)
        self.assertEqual(len(response.data[0]["options"]), 5)

    def test_customer_cannot_select_another_customers_option(self):
        option = self.other_recommendation.option.order_by(
            "option_date", "option_time"
        ).first()
        self.client.force_authenticate(user=self.customer)
        response = self.client.post(
            reverse(
                "api_customer_reschedule_option_select",
                kwargs={"option_id": option.id},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.other_recommendation.refresh_from_db()
        self.assertEqual(
            self.other_recommendation.status,
            RescheduleRecommendation.PENDING,
        )

    def test_customer_selection_applies_reschedule_and_requires_fresh_check_in(self):
        option = self.recommendation.option.order_by(
            "option_date", "option_time"
        ).first()
        self.client.force_authenticate(user=self.customer)
        response = self.client.post(
            reverse(
                "api_customer_reschedule_option_select",
                kwargs={"option_id": option.id},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], RescheduleRecommendation.APPLIED)

        self.booking.refresh_from_db()
        ticket = QueueTicket.objects.get(booking=self.booking)
        self.assertEqual(self.booking.booking_date, option.option_date)
        self.assertEqual(self.booking.booking_time, option.option_time)
        self.assertEqual(self.booking.status, Booking.PENDING)
        self.assertIsNone(self.booking.checked_in_at)
        self.assertEqual(ticket.status, QueueTicket.SCHEDULED)
        self.assertEqual(ticket.queue_type, QueueTicket.PRIORITY)
        self.assertTrue(ticket.queue_number.startswith("P"))
        self.assertTrue(
            Notification.objects.filter(
                user=self.customer,
                notification_type=Notification.RESCHEDULE,
                related_ticket=ticket,
                title="Reschedule confirmed",
            ).exists()
        )

    def test_stale_slot_failure_rolls_back_selection_and_approval(self):
        option = self.recommendation.option.order_by(
            "option_date", "option_time"
        ).first()

        # Fill the destination after the recommendation was generated. The API
        # must reject the stale option and leave no partial APPROVED selection.
        for index in range(2):
            user = self._create_customer(f"future{index}")
            Booking.objects.create(
                user=user,
                branch=self.branch,
                service=self.service,
                booking_date=option.option_date,
                booking_time=option.option_time,
                status=Booking.PENDING,
                source=Booking.ONLINE,
            )

        self.client.force_authenticate(user=self.customer)
        response = self.client.post(
            reverse(
                "api_customer_reschedule_option_select",
                kwargs={"option_id": option.id},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["code"], "slot_full")
        self.recommendation.refresh_from_db()
        option.refresh_from_db()
        self.booking.refresh_from_db()
        self.assertEqual(
            self.recommendation.status,
            RescheduleRecommendation.PENDING,
        )
        self.assertFalse(option.is_selected)
        self.assertEqual(self.booking.booking_date, timezone.localdate())
        self.assertIsNotNone(self.booking.checked_in_at)

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

from .models import RescheduleOption, RescheduleRecommendation
from .services import apply_approved_reschedule, select_reschedule_option


class Day35DisruptionReschedulingTests(APITestCase):
    """Regression coverage for repaired disruption/rescheduling workflows."""

    def setUp(self):
        self.today = timezone.localdate()
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
            average_service_time=10,
            is_active=True,
        )
        self.unmapped_service = Service.objects.create(
            service_code="PASS01",
            name="Passport",
            description="Passport service",
            average_service_time=10,
            is_active=True,
        )
        BranchService.objects.create(
            branch=self.branch,
            service=self.service,
            max_bookings_per_slot=2,
        )

        self.manager = User.objects.create_user(username="manager", password="pw")
        Profile.objects.create(
            user=self.manager,
            date_of_birth=date(1985, 1, 1),
            gender=Profile.OTHER,
            role=Profile.BRANCH_MANAGER,
            branch=self.branch,
        )
        self.other_manager = User.objects.create_user(
            username="othermanager", password="pw"
        )
        Profile.objects.create(
            user=self.other_manager,
            date_of_birth=date(1986, 1, 1),
            gender=Profile.OTHER,
            role=Profile.BRANCH_MANAGER,
            branch=self.other_branch,
        )
        self.staff = User.objects.create_user(username="staff", password="pw")
        Profile.objects.create(
            user=self.staff,
            date_of_birth=date(1990, 1, 1),
            gender=Profile.OTHER,
            role=Profile.COUNTER_STAFF,
            branch=self.branch,
        )

        self.bookings = []
        self.tickets = []
        for index in range(4):
            user = User.objects.create_user(
                username=f"customer{index + 1}",
                password="pw",
            )
            Profile.objects.create(
                user=user,
                date_of_birth=date(1995, 1, 1),
                gender=Profile.OTHER,
                role=Profile.CUSTOMER,
            )
            booking = Booking.objects.create(
                user=user,
                branch=self.branch,
                service=self.service,
                booking_date=self.today,
                booking_time=time(9, 0),
                status=Booking.CONFIRMED,
                source=Booking.ONLINE,
                checked_in_at=timezone.now() - timedelta(minutes=45),
            )
            ticket = QueueTicket.objects.create(
                booking=booking,
                queue_number=f"A{index + 1:03d}",
                queue_type=QueueTicket.GENERAL,
                status=QueueTicket.WAITING,
            )
            self.bookings.append(booking)
            self.tickets.append(ticket)

    def _create_pause(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.post(
            reverse(
                "api_branch_queue_pause_create",
                kwargs={"branch_id": self.branch.id},
            ),
            {
                "service_id": self.service.id,
                "booking_date": self.today.isoformat(),
                "reason": "Network outage",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        queue_pause = QueuePause.objects.get(pk=response.data["pause_impact"]["id"])
        QueuePause.objects.filter(pk=queue_pause.pk).update(
            started_at=timezone.now() - timedelta(minutes=30)
        )
        queue_pause.refresh_from_db()
        return queue_pause

    def test_manager_can_create_pause_only_for_offered_service(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.post(
            reverse(
                "api_branch_queue_pause_create",
                kwargs={"branch_id": self.branch.id},
            ),
            {
                "service_id": self.unmapped_service.id,
                "booking_date": self.today.isoformat(),
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(QueuePause.objects.count(), 0)

    def test_branch_manager_cannot_pause_another_branch(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.post(
            reverse(
                "api_branch_queue_pause_create",
                kwargs={"branch_id": self.other_branch.id},
            ),
            {
                "service_id": self.service.id,
                "booking_date": self.today.isoformat(),
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_counter_staff_cannot_create_disruption(self):
        self.client.force_authenticate(user=self.staff)
        response = self.client.post(
            reverse(
                "api_branch_queue_pause_create",
                kwargs={"branch_id": self.branch.id},
            ),
            {
                "service_id": self.service.id,
                "booking_date": self.today.isoformat(),
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_live_preview_marks_tail_customers_at_reschedule_risk(self):
        queue_pause = self._create_pause()
        self.client.force_authenticate(user=self.manager)
        response = self.client.get(
            reverse("api_queue_pause_detail", kwargs={"pause_id": queue_pause.id})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["affected_waiting_count"], 4)
        self.assertEqual(response.data["reschedule_risk_count"], 3)
        self.assertEqual(
            response.data["reschedule_risk_tickets"],
            ["A002", "A003", "A004"],
        )

    def test_resume_finalizes_impacts_notifications_and_recommendations(self):
        queue_pause = self._create_pause()
        self.client.force_authenticate(user=self.manager)
        response = self.client.post(
            reverse("api_queue_pause_resume", kwargs={"pause_id": queue_pause.id})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        queue_pause.refresh_from_db()
        self.assertFalse(queue_pause.is_active)

        self.assertEqual(
            QueueDisruptionImpact.objects.filter(
                queue_pause=queue_pause,
                impact_type=QueueDisruptionImpact.AFFECTED,
            ).count(),
            4,
        )
        self.assertEqual(
            QueueDisruptionImpact.objects.filter(
                queue_pause=queue_pause,
                impact_type=QueueDisruptionImpact.RESCHEDULE_RISK,
            ).count(),
            3,
        )
        self.assertEqual(
            RescheduleRecommendation.objects.filter(
                disruption_impact__queue_pause=queue_pause
            ).count(),
            3,
        )

        recommendations = RescheduleRecommendation.objects.filter(
            disruption_impact__queue_pause=queue_pause
        )
        for recommendation in recommendations:
            self.assertTrue(recommendation.priority_on_reschedule)
            self.assertEqual(recommendation.status, RescheduleRecommendation.PENDING)
            self.assertEqual(recommendation.option.count(), 5)
            first = recommendation.option.order_by("option_date", "option_time").first()
            self.assertEqual(first.capacity, 2)
            self.assertIsInstance(first.option_time, time)

        # Four affected + three risk notifications are supported for registered users.
        self.assertEqual(Notification.objects.filter(related_impact__queue_pause=queue_pause).count(), 7)

    def test_repeated_resume_processing_is_idempotent(self):
        queue_pause = self._create_pause()
        self.client.force_authenticate(user=self.manager)
        url = reverse("api_queue_pause_resume", kwargs={"pause_id": queue_pause.id})

        first_response = self.client.post(url)
        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        impact_count = QueueDisruptionImpact.objects.filter(queue_pause=queue_pause).count()
        recommendation_count = RescheduleRecommendation.objects.filter(
            disruption_impact__queue_pause=queue_pause
        ).count()
        notification_count = Notification.objects.filter(
            related_impact__queue_pause=queue_pause
        ).count()

        second_response = self.client.post(url)
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            QueueDisruptionImpact.objects.filter(queue_pause=queue_pause).count(),
            impact_count,
        )
        self.assertEqual(
            RescheduleRecommendation.objects.filter(
                disruption_impact__queue_pause=queue_pause
            ).count(),
            recommendation_count,
        )
        self.assertEqual(
            Notification.objects.filter(related_impact__queue_pause=queue_pause).count(),
            notification_count,
        )

    def test_selected_option_applies_as_priority_but_returns_to_scheduled(self):
        queue_pause = self._create_pause()
        self.client.force_authenticate(user=self.manager)
        response = self.client.post(
            reverse("api_queue_pause_resume", kwargs={"pause_id": queue_pause.id})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        recommendation = RescheduleRecommendation.objects.filter(
            disruption_impact__queue_pause=queue_pause
        ).order_by("id").first()
        option = recommendation.option.order_by("option_date", "option_time").first()
        selected, error = select_reschedule_option(option)
        self.assertIsNone(error)
        self.assertEqual(selected.id, option.id)

        applied, error = apply_approved_reschedule(recommendation)
        self.assertIsNone(error)
        self.assertEqual(applied.status, RescheduleRecommendation.APPLIED)

        booking = applied.booking
        booking.refresh_from_db()
        ticket = QueueTicket.objects.get(booking=booking)
        self.assertEqual(booking.booking_date, option.option_date)
        self.assertEqual(booking.booking_time, option.option_time)
        self.assertIsNone(booking.checked_in_at)
        self.assertEqual(booking.status, Booking.PENDING)
        self.assertEqual(ticket.queue_type, QueueTicket.PRIORITY)
        self.assertTrue(ticket.queue_number.startswith("P"))
        self.assertEqual(ticket.status, QueueTicket.SCHEDULED)
        self.assertIsNone(ticket.assigned_counter_id)

    def test_selection_rechecks_capacity_instead_of_trusting_stale_option_snapshot(self):
        queue_pause = self._create_pause()
        self.client.force_authenticate(user=self.manager)
        self.client.post(
            reverse("api_queue_pause_resume", kwargs={"pause_id": queue_pause.id})
        )

        recommendation = RescheduleRecommendation.objects.filter(
            disruption_impact__queue_pause=queue_pause
        ).first()
        option = recommendation.option.order_by("option_date", "option_time").first()

        # Consume both slots after the recommendation was generated. The stored
        # available_count is now stale, so selection must query current capacity.
        for index in range(2):
            user = User.objects.create_user(username=f"future{index}", password="pw")
            Profile.objects.create(
                user=user,
                date_of_birth=date(1994, 1, 1),
                gender=Profile.OTHER,
                role=Profile.CUSTOMER,
            )
            Booking.objects.create(
                user=user,
                branch=self.branch,
                service=self.service,
                booking_date=option.option_date,
                booking_time=option.option_time,
                status=Booking.PENDING,
                source=Booking.ONLINE,
            )

        selected, error = select_reschedule_option(option)
        self.assertIsNone(selected)
        self.assertEqual(error, "slot_full")

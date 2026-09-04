from datetime import date, time
from pathlib import Path

from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Profile
from bookings.models import Booking
from branches.models import Branch
from queues.models import QueueEvent, QueueTicket
from services.models import BranchService, Service


class Day43CustomerDashboardTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(
            branch_code="PTA01",
            name="Pretoria Central",
            address="1 Main Street",
            city="Pretoria",
            opening_time=time(8, 0),
            closing_time=time(17, 0),
            is_active=True,
        )
        self.service = Service.objects.create(
            service_code="ID01",
            name="ID Application",
            description="Identity document application",
            average_service_time=10,
            is_active=True,
        )
        BranchService.objects.create(
            branch=self.branch,
            service=self.service,
            max_bookings_per_slot=4,
            is_active=True,
        )
        self.customer = User.objects.create_user(
            username="customer43",
            password="pw",
            first_name="Thato",
            last_name="Mokoena",
        )
        Profile.objects.create(
            user=self.customer,
            date_of_birth=date(1995, 5, 10),
            gender=Profile.OTHER,
            role=Profile.CUSTOMER,
        )
        self.other_customer = User.objects.create_user(username="other43", password="pw")
        Profile.objects.create(
            user=self.other_customer,
            date_of_birth=date(1994, 4, 9),
            gender=Profile.OTHER,
            role=Profile.CUSTOMER,
        )

        now = timezone.now()
        appointment_time = timezone.localtime(now).time().replace(second=0, microsecond=0)
        self.booking = Booking.objects.create(
            user=self.customer,
            branch=self.branch,
            service=self.service,
            booking_date=timezone.localdate(),
            booking_time=appointment_time,
            status=Booking.PENDING,
            source=Booking.ONLINE,
            checked_in_at=now,
        )
        QueueTicket.objects.create(
            booking=self.booking,
            queue_number="A001",
            queue_type=QueueTicket.GENERAL,
            status=QueueTicket.WAITING,
        )
        other_booking = Booking.objects.create(
            user=self.other_customer,
            branch=self.branch,
            service=self.service,
            booking_date=timezone.localdate(),
            booking_time=appointment_time,
            status=Booking.CONFIRMED,
            source=Booking.ONLINE,
        )
        QueueTicket.objects.create(
            booking=other_booking,
            queue_number="A002",
            queue_type=QueueTicket.GENERAL,
            status=QueueTicket.SCHEDULED,
        )

    def test_customer_workspace_renders_dashboard_contract(self):
        response = self.client.get(reverse("frontend_customer_workspace"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "My Smart Q")
        self.assertContains(response, "data-customer-dashboard")
        self.assertContains(response, "data-queue-panel")
        self.assertContains(response, "data-queue-join-form")
        self.assertContains(response, "data-queue-leave")
        self.assertContains(response, "Join a live queue")
        self.assertContains(response, "data-upcoming-body")
        self.assertContains(response, "data-history-body")
        self.assertContains(response, "/static/css/customer-dashboard.css")
        self.assertContains(response, "/static/js/pages/customer-dashboard.js")

    def test_customer_dashboard_assets_are_discoverable(self):
        self.assertIsNotNone(finders.find("css/customer-dashboard.css"))
        self.assertIsNotNone(finders.find("js/pages/customer-dashboard.js"))

    def test_customer_dashboard_javascript_targets_walk_in_api(self):
        source = Path(finders.find("js/pages/customer-dashboard.js")).read_text(encoding="utf-8")
        self.assertIn('/api/v1/bookings/walk-ins/', source)
        self.assertIn("data-queue-join-form", source)
        self.assertIn("data-queue-leave", source)

    def test_customer_booking_and_queue_contract_is_ownership_scoped(self):
        self.client.force_login(self.customer)
        bookings_response = self.client.get(reverse("api_my_booking_list"))
        self.assertEqual(bookings_response.status_code, 200)
        self.assertEqual(len(bookings_response.json()), 1)
        self.assertEqual(bookings_response.json()[0]["id"], self.booking.id)
        self.assertEqual(bookings_response.json()[0]["queue_ticket"]["queue_number"], "A001")

        queue_response = self.client.get(reverse("api_my_current_queue_ticket"))
        self.assertEqual(queue_response.status_code, 200)
        payload = queue_response.json()
        self.assertEqual(payload["ticket"]["booking_id"], self.booking.id)
        self.assertEqual(payload["ticket"]["queue_number"], "A001")
        self.assertEqual(payload["prediction"]["queue_position"], 1)
        self.assertEqual(payload["prediction"]["people_ahead"], 0)
        self.assertEqual(payload["prediction"]["estimated_wait_time"], 0)

    def test_customer_can_join_live_queue_without_appointment(self):
        self.client.force_login(self.other_customer)
        response = self.client.post(
            reverse("api_customer_walk_in"),
            {"branch": self.branch.id, "service": self.service.id},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["source"], Booking.WALK_IN)
        self.assertTrue(payload["is_checked_in"])
        self.assertEqual(payload["queue_ticket"]["status"], QueueTicket.WAITING)
        booking = Booking.objects.get(pk=payload["id"])
        self.assertEqual(booking.user, self.other_customer)
        self.assertIsNone(booking.guest_customer_id)
        self.assertEqual(booking.branch, self.branch)
        self.assertEqual(booking.service, self.service)
        self.assertEqual(booking.queueticket.status, QueueTicket.WAITING)
        event = QueueEvent.objects.filter(booking=booking, event_type=QueueEvent.CHECKED_IN).get()
        self.assertEqual(event.metadata["check_in_mode"], "walk_in_customer")

    def test_customer_can_leave_waiting_walk_in_queue(self):
        self.client.force_login(self.other_customer)
        joined = self.client.post(
            reverse("api_customer_walk_in"),
            {"branch": self.branch.id, "service": self.service.id},
            content_type="application/json",
        )
        self.assertEqual(joined.status_code, 201)
        booking_id = joined.json()["id"]

        cancelled = self.client.patch(
            reverse("api_booking_cancel", kwargs={"pk": booking_id}),
            {},
            content_type="application/json",
        )
        self.assertEqual(cancelled.status_code, 200)
        booking = Booking.objects.get(pk=booking_id)
        self.assertEqual(booking.status, Booking.CANCELLED)
        self.assertEqual(booking.queueticket.status, QueueTicket.CANCELLED)
        self.assertEqual(self.client.get(reverse("api_my_current_queue_ticket")).status_code, 404)

    def test_customer_cannot_create_second_active_live_queue(self):
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse("api_customer_walk_in"),
            {"branch": self.branch.id, "service": self.service.id},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("already have an active queue ticket", response.json()["detail"])
        self.assertEqual(
            QueueTicket.objects.filter(
                booking__user=self.customer,
                status__in=[QueueTicket.WAITING, QueueTicket.SERVING],
            ).count(),
            1,
        )

    def test_staff_account_cannot_use_customer_walk_in_api(self):
        staff = User.objects.create_user(username="staff43", password="pw")
        Profile.objects.create(
            user=staff,
            date_of_birth=date(1990, 1, 1),
            gender=Profile.OTHER,
            role=Profile.RECEPTIONIST,
            branch=self.branch,
        )
        self.client.force_login(staff)
        response = self.client.post(
            reverse("api_customer_walk_in"),
            {"branch": self.branch.id, "service": self.service.id},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_manager_route_does_not_render_customer_dashboard(self):
        response = self.client.get(reverse("frontend_manager_workspace"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "data-customer-dashboard")
        self.assertNotContains(response, "/static/css/customer-dashboard.css")

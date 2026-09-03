from datetime import date, time

from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Profile
from bookings.models import Booking
from branches.models import Branch
from queues.models import QueueTicket
from services.models import Service


class Day43CustomerDashboardTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(branch_code="PTA01", name="Pretoria Central", address="1 Main Street", city="Pretoria", opening_time=time(8, 0), closing_time=time(17, 0), is_active=True)
        self.service = Service.objects.create(service_code="ID01", name="ID Application", description="Identity document application", average_service_time=10, is_active=True)
        self.customer = User.objects.create_user(username="customer43", password="pw", first_name="Thato", last_name="Mokoena")
        Profile.objects.create(user=self.customer, date_of_birth=date(1995, 5, 10), gender=Profile.OTHER, role=Profile.CUSTOMER)
        self.other_customer = User.objects.create_user(username="other43", password="pw")
        Profile.objects.create(user=self.other_customer, date_of_birth=date(1994, 4, 9), gender=Profile.OTHER, role=Profile.CUSTOMER)

        now = timezone.now()
        appointment_time = timezone.localtime(now).time().replace(second=0, microsecond=0)
        self.booking = Booking.objects.create(user=self.customer, branch=self.branch, service=self.service, booking_date=timezone.localdate(), booking_time=appointment_time, status=Booking.PENDING, source=Booking.ONLINE, checked_in_at=now)
        QueueTicket.objects.create(booking=self.booking, queue_number="A001", queue_type=QueueTicket.GENERAL, status=QueueTicket.WAITING)
        other_booking = Booking.objects.create(user=self.other_customer, branch=self.branch, service=self.service, booking_date=timezone.localdate(), booking_time=appointment_time, status=Booking.CONFIRMED, source=Booking.ONLINE)
        QueueTicket.objects.create(booking=other_booking, queue_number="A002", queue_type=QueueTicket.GENERAL, status=QueueTicket.SCHEDULED)

    def test_customer_workspace_renders_dashboard_contract(self):
        response = self.client.get(reverse("frontend_customer_workspace"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "My Smart Q")
        self.assertContains(response, "data-customer-dashboard")
        self.assertContains(response, "data-queue-panel")
        self.assertContains(response, "data-upcoming-body")
        self.assertContains(response, "data-history-body")
        self.assertContains(response, "/static/css/customer-dashboard.css")
        self.assertContains(response, "/static/js/pages/customer-dashboard.js")

    def test_customer_dashboard_assets_are_discoverable(self):
        self.assertIsNotNone(finders.find("css/customer-dashboard.css"))
        self.assertIsNotNone(finders.find("js/pages/customer-dashboard.js"))

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

    def test_manager_route_does_not_render_customer_dashboard(self):
        response = self.client.get(reverse("frontend_manager_workspace"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "data-customer-dashboard")
        self.assertNotContains(response, "/static/css/customer-dashboard.css")

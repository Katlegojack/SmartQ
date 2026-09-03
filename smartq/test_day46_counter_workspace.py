from datetime import date, time

from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Profile
from bookings.models import Booking
from branches.models import Branch
from counters.models import Counter
from queues.models import QueueTicket
from services.models import Service


class Day46CounterWorkspaceTests(APITestCase):
    def setUp(self):
        self.branch = Branch.objects.create(
            branch_code="CNT46",
            name="Day 46 Counter Branch",
            address="46 Main Street",
            city="Kimberley",
            opening_time=time(8, 0),
            closing_time=time(16, 0),
            is_active=True,
        )
        self.service = Service.objects.create(
            service_code="CNT46S",
            name="Counter Service",
            description="Day 46 serving workflow service",
            average_service_time=12,
            is_active=True,
        )
        self.staff = User.objects.create_user(
            username="day46staff",
            password="SafePassword123!",
            first_name="Karabo",
        )
        Profile.objects.create(
            user=self.staff,
            date_of_birth=date(1992, 5, 5),
            gender=Profile.OTHER,
            role=Profile.COUNTER_STAFF,
            branch=self.branch,
        )
        self.other_staff = User.objects.create_user(
            username="day46otherstaff",
            password="SafePassword123!",
        )
        Profile.objects.create(
            user=self.other_staff,
            date_of_birth=date(1993, 6, 6),
            gender=Profile.OTHER,
            role=Profile.COUNTER_STAFF,
            branch=self.branch,
        )
        self.customer = User.objects.create_user(
            username="day46customer",
            password="SafePassword123!",
            first_name="Lebo",
            last_name="Mokoena",
        )
        Profile.objects.create(
            user=self.customer,
            date_of_birth=date(1996, 4, 10),
            gender=Profile.OTHER,
            role=Profile.CUSTOMER,
        )
        self.counter = Counter.objects.create(
            branch=self.branch,
            counter_number="4",
            queue_type=QueueTicket.GENERAL,
            assigned_staff=self.staff,
            status=Counter.CLOSED,
        )

    def authenticate_staff(self, staff=None):
        self.client.force_authenticate(staff or self.staff)

    def create_waiting_ticket(self, *, queue_number="A046", queue_type=QueueTicket.GENERAL):
        booking = Booking.objects.create(
            user=self.customer,
            branch=self.branch,
            service=self.service,
            booking_date=timezone.localdate(),
            booking_time=time(9, 0),
            status=Booking.PENDING,
            checked_in_at=timezone.now(),
        )
        ticket = QueueTicket.objects.create(
            booking=booking,
            queue_number=queue_number,
            queue_type=queue_type,
            status=QueueTicket.WAITING,
        )
        return booking, ticket

    def test_counter_route_renders_dedicated_day46_workspace(self):
        response = self.client.get(reverse("frontend_counter_workspace"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, "Counter staff workspace")
        self.assertContains(response, "data-counter-workspace")
        self.assertContains(response, "data-call-next")
        self.assertContains(response, "data-complete-current")
        self.assertContains(response, "data-no-show-current")
        self.assertContains(response, 'data-counter-action="pause"')
        self.assertNotContains(response, "Manager analytics")
        self.assertNotContains(response, "System administration")

    def test_day46_counter_assets_are_discoverable(self):
        self.assertIsNotNone(finders.find("css/counter-workspace.css"))
        self.assertIsNotNone(finders.find("js/pages/counter-workspace.js"))

    def test_counter_staff_without_assignment_gets_explicit_404(self):
        self.counter.assigned_staff = None
        self.counter.save(update_fields=["assigned_staff"])
        self.authenticate_staff()

        response = self.client.get(reverse("api_my_assigned_counter"))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("not currently assigned", response.data["detail"])

    def test_assigned_staff_can_open_call_complete_and_return_counter_to_free_state(self):
        _, waiting_ticket = self.create_waiting_ticket()
        self.authenticate_staff()

        opened = self.client.post(reverse("api_counter_open", args=[self.counter.id]))
        called = self.client.post(reverse("api_call_next_ticket", args=[self.counter.id]))
        current = self.client.get(reverse("api_current_counter_ticket", args=[self.counter.id]))
        completed = self.client.post(reverse("api_complete_current_ticket", args=[self.counter.id]))
        current_after = self.client.get(reverse("api_current_counter_ticket", args=[self.counter.id]))

        self.assertEqual(opened.status_code, status.HTTP_200_OK)
        self.assertEqual(called.status_code, status.HTTP_200_OK)
        self.assertEqual(called.data["id"], waiting_ticket.id)
        self.assertEqual(called.data["status"], QueueTicket.SERVING)
        self.assertEqual(called.data["assigned_counter"], self.counter.id)
        self.assertEqual(current.status_code, status.HTTP_200_OK)
        self.assertEqual(current.data["id"], waiting_ticket.id)
        self.assertEqual(completed.status_code, status.HTTP_200_OK)
        self.assertEqual(completed.data["status"], QueueTicket.COMPLETED)
        self.assertIsNone(completed.data["assigned_counter"])
        self.assertEqual(current_after.status_code, status.HTTP_404_NOT_FOUND)

    def test_paused_counter_can_finish_current_customer_as_no_show_but_cannot_call_next(self):
        booking, ticket = self.create_waiting_ticket()
        self.counter.status = Counter.PAUSED
        self.counter.save(update_fields=["status"])
        ticket.status = QueueTicket.SERVING
        ticket.assigned_counter = self.counter
        ticket.save(update_fields=["status", "assigned_counter"])
        booking.status = Booking.CONFIRMED
        booking.save(update_fields=["status"])
        self.authenticate_staff()

        call_response = self.client.post(reverse("api_call_next_ticket", args=[self.counter.id]))
        no_show_response = self.client.post(reverse("api_no_show_current_ticket", args=[self.counter.id]))

        self.assertEqual(call_response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(no_show_response.status_code, status.HTTP_200_OK)
        self.assertEqual(no_show_response.data["status"], QueueTicket.NO_SHOW)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.NO_SHOW)

    def test_counter_queue_type_controls_which_waiting_customer_is_called(self):
        general_booking, general_ticket = self.create_waiting_ticket(
            queue_number="A047",
            queue_type=QueueTicket.GENERAL,
        )
        priority_customer = User.objects.create_user(
            username="day46priority",
            password="SafePassword123!",
            first_name="Priority",
            last_name="Customer",
        )
        Profile.objects.create(
            user=priority_customer,
            date_of_birth=date(1960, 1, 1),
            gender=Profile.OTHER,
            role=Profile.CUSTOMER,
        )
        priority_booking = Booking.objects.create(
            user=priority_customer,
            branch=self.branch,
            service=self.service,
            booking_date=timezone.localdate(),
            booking_time=time(9, 15),
            status=Booking.PENDING,
            checked_in_at=timezone.now(),
        )
        priority_ticket = QueueTicket.objects.create(
            booking=priority_booking,
            queue_number="P046",
            queue_type=QueueTicket.PRIORITY,
            status=QueueTicket.WAITING,
        )
        self.counter.queue_type = QueueTicket.PRIORITY
        self.counter.status = Counter.OPEN
        self.counter.save(update_fields=["queue_type", "status"])
        self.authenticate_staff()

        response = self.client.post(reverse("api_call_next_ticket", args=[self.counter.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], priority_ticket.id)
        general_ticket.refresh_from_db()
        self.assertEqual(general_ticket.status, QueueTicket.WAITING)
        general_booking.refresh_from_db()
        self.assertEqual(general_booking.status, Booking.PENDING)

    def test_other_counter_staff_cannot_operate_this_staff_members_counter(self):
        self.counter.status = Counter.OPEN
        self.counter.save(update_fields=["status"])
        self.create_waiting_ticket()
        self.authenticate_staff(self.other_staff)

        response = self.client.post(reverse("api_call_next_ticket", args=[self.counter.id]))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

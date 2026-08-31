from datetime import date, time

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounts.models import Profile
from bookings.models import Booking
from branches.models import Branch
from queues.models import QueueTicket
from services.models import Service
from .models import Counter
from .services import get_active_counter_count


class CounterLifecycleAPITests(APITestCase):
    """Day 33 regression coverage for counter staff assignment and lifecycle."""

    def setUp(self):
        self.branch = Branch.objects.create(
            branch_code="KIM01",
            name="Kimberley Branch",
            address="1 Test Street",
            city="Kimberley",
            opening_time=time(8, 0),
            closing_time=time(16, 30),
            is_active=True,
        )
        self.other_branch = Branch.objects.create(
            branch_code="PTA01",
            name="Pretoria Branch",
            address="2 Test Street",
            city="Pretoria",
            opening_time=time(8, 0),
            closing_time=time(16, 30),
            is_active=True,
        )

        self.manager = User.objects.create_user(username="manager", password="pw")
        Profile.objects.create(
            user=self.manager,
            date_of_birth=date(1985, 1, 1),
            gender=Profile.OTHER,
            role=Profile.BRANCH_MANAGER,
            branch=self.branch,
        )
        self.staff = User.objects.create_user(username="staff", password="pw")
        Profile.objects.create(
            user=self.staff,
            date_of_birth=date(1990, 1, 1),
            gender=Profile.OTHER,
            role=Profile.COUNTER_STAFF,
            branch=self.branch,
        )
        self.second_staff = User.objects.create_user(username="staff2", password="pw")
        Profile.objects.create(
            user=self.second_staff,
            date_of_birth=date(1991, 1, 1),
            gender=Profile.OTHER,
            role=Profile.COUNTER_STAFF,
            branch=self.branch,
        )
        self.other_staff = User.objects.create_user(username="otherstaff", password="pw")
        Profile.objects.create(
            user=self.other_staff,
            date_of_birth=date(1992, 1, 1),
            gender=Profile.OTHER,
            role=Profile.COUNTER_STAFF,
            branch=self.other_branch,
        )
        self.customer = User.objects.create_user(username="customer", password="pw")
        Profile.objects.create(
            user=self.customer,
            date_of_birth=date(1995, 1, 1),
            gender=Profile.OTHER,
            role=Profile.CUSTOMER,
        )

        self.counter = Counter.objects.create(
            branch=self.branch,
            counter_number="1",
            queue_type=QueueTicket.GENERAL,
            status=Counter.CLOSED,
        )
        self.second_counter = Counter.objects.create(
            branch=self.branch,
            counter_number="2",
            queue_type=QueueTicket.GENERAL,
            status=Counter.CLOSED,
        )
        self.client = APIClient()

    def _assign_staff(self, counter=None, staff=None):
        counter = counter or self.counter
        staff = staff or self.staff
        self.client.force_authenticate(user=self.manager)
        return self.client.post(
            reverse("api_counter_assign_staff", kwargs={"counter_id": counter.id}),
            {"staff_user_id": staff.id},
            format="json",
        )

    def test_branch_manager_can_assign_same_branch_counter_staff(self):
        response = self._assign_staff()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.counter.refresh_from_db()
        self.assertEqual(self.counter.assigned_staff, self.staff)

    def test_counter_staff_cannot_self_assign(self):
        self.client.force_authenticate(user=self.staff)
        response = self.client.post(
            reverse("api_counter_assign_staff", kwargs={"counter_id": self.counter.id}),
            {"staff_user_id": self.staff.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_cannot_assign_staff_from_another_branch(self):
        response = self._assign_staff(staff=self.other_staff)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_one_staff_member_cannot_be_assigned_to_two_counters(self):
        first = self._assign_staff(counter=self.counter, staff=self.staff)
        second = self._assign_staff(counter=self.second_counter, staff=self.staff)
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_409_CONFLICT)

    def test_unassigned_counter_cannot_open(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.post(
            reverse("api_counter_open", kwargs={"counter_id": self.counter.id})
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_assigned_staff_can_open_pause_resume_and_close_own_counter(self):
        self._assign_staff()
        self.client.force_authenticate(user=self.staff)

        opened = self.client.post(
            reverse("api_counter_open", kwargs={"counter_id": self.counter.id})
        )
        paused = self.client.post(
            reverse("api_counter_pause", kwargs={"counter_id": self.counter.id})
        )
        resumed = self.client.post(
            reverse("api_counter_resume", kwargs={"counter_id": self.counter.id})
        )
        closed = self.client.post(
            reverse("api_counter_close", kwargs={"counter_id": self.counter.id})
        )

        self.assertEqual(opened.status_code, status.HTTP_200_OK)
        self.assertEqual(paused.status_code, status.HTTP_200_OK)
        self.assertEqual(resumed.status_code, status.HTTP_200_OK)
        self.assertEqual(closed.status_code, status.HTTP_200_OK)
        self.counter.refresh_from_db()
        self.assertEqual(self.counter.status, Counter.CLOSED)

    def test_counter_staff_cannot_operate_another_same_branch_counter(self):
        self._assign_staff(counter=self.counter, staff=self.staff)
        self._assign_staff(counter=self.second_counter, staff=self.second_staff)
        self.client.force_authenticate(user=self.staff)

        response = self.client.post(
            reverse("api_counter_open", kwargs={"counter_id": self.second_counter.id})
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_paused_counter_can_finish_current_customer_but_cannot_call_next(self):
        self._assign_staff()
        self.counter.status = Counter.PAUSED
        self.counter.save(update_fields=["status"])

        service = Service.objects.create(
            service_code="ID01",
            name="ID Application",
            description="Identity document service",
            average_service_time=10,
        )
        booking = Booking.objects.create(
            user=self.customer,
            branch=self.branch,
            service=service,
            booking_date=date.today(),
            booking_time=time(9, 0),
            status=Booking.CONFIRMED,
        )
        ticket = QueueTicket.objects.create(
            booking=booking,
            queue_number="A001",
            queue_type=QueueTicket.GENERAL,
            status=QueueTicket.SERVING,
            assigned_counter=self.counter,
        )

        self.client.force_authenticate(user=self.staff)
        call_response = self.client.post(
            reverse("api_call_next_ticket", kwargs={"counter_id": self.counter.id})
        )
        complete_response = self.client.post(
            reverse("api_complete_current_ticket", kwargs={"counter_id": self.counter.id})
        )

        self.assertEqual(call_response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(complete_response.status_code, status.HTTP_200_OK)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, QueueTicket.COMPLETED)

    def test_busy_counter_cannot_close_or_change_assignment(self):
        self._assign_staff()
        self.counter.status = Counter.OPEN
        self.counter.save(update_fields=["status"])

        service = Service.objects.create(
            service_code="ID02",
            name="Collection",
            description="Collection service",
            average_service_time=10,
        )
        booking = Booking.objects.create(
            user=self.customer,
            branch=self.branch,
            service=service,
            booking_date=date.today(),
            booking_time=time(9, 0),
            status=Booking.CONFIRMED,
        )
        QueueTicket.objects.create(
            booking=booking,
            queue_number="A002",
            queue_type=QueueTicket.GENERAL,
            status=QueueTicket.SERVING,
            assigned_counter=self.counter,
        )

        self.client.force_authenticate(user=self.staff)
        close_response = self.client.post(
            reverse("api_counter_close", kwargs={"counter_id": self.counter.id})
        )
        self.client.force_authenticate(user=self.manager)
        unassign_response = self.client.post(
            reverse("api_counter_unassign_staff", kwargs={"counter_id": self.counter.id})
        )

        self.assertEqual(close_response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(unassign_response.status_code, status.HTTP_409_CONFLICT)

    def test_only_staffed_open_counters_count_as_active_capacity(self):
        self.counter.status = Counter.OPEN
        self.counter.save(update_fields=["status"])
        self.assertEqual(
            get_active_counter_count(self.branch, QueueTicket.GENERAL),
            0,
        )

        self.counter.assigned_staff = self.staff
        self.counter.save(update_fields=["assigned_staff"])
        self.assertEqual(
            get_active_counter_count(self.branch, QueueTicket.GENERAL),
            1,
        )

    def test_counter_staff_can_read_their_assignment(self):
        self._assign_staff()
        self.client.force_authenticate(user=self.staff)
        response = self.client.get(reverse("api_my_assigned_counter"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.counter.id)
        self.assertEqual(response.data["assigned_staff"], self.staff.id)

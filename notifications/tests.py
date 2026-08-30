from datetime import date, datetime, time

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from accounts.models import Profile
from bookings.models import Booking
from branches.models import Branch
from queues.models import QueueTicket
from services.models import Service
from .models import Notification
from .services import create_due_check_in_reminders


class CheckInReminderServiceTests(TestCase):
    """Regression tests for the six-hour hourly reminder policy."""

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
        self.service = Service.objects.create(
            service_code="ID01",
            name="ID Application",
            description="Identity document service",
            average_service_time=10,
            is_active=True,
        )
        self.user = User.objects.create_user(username="customer", password="pw")
        Profile.objects.create(
            user=self.user,
            date_of_birth=date(1995, 1, 1),
            gender=Profile.OTHER,
            role=Profile.CUSTOMER,
        )
        self.booking = Booking.objects.create(
            user=self.user,
            branch=self.branch,
            service=self.service,
            booking_date=timezone.localdate(),
            booking_time=time(15, 0),
            source=Booking.ONLINE,
            status=Booking.PENDING,
        )
        self.ticket = QueueTicket.objects.create(
            booking=self.booking,
            queue_number="A001",
            queue_type=QueueTicket.GENERAL,
            status=QueueTicket.SCHEDULED,
        )

    def _aware_today(self, hour, minute=0):
        value = datetime.combine(timezone.localdate(), time(hour, minute))
        return timezone.make_aware(value, timezone.get_current_timezone())

    def test_first_reminder_is_created_six_hours_before_appointment(self):
        result = create_due_check_in_reminders(now=self._aware_today(9, 5))

        self.assertEqual(result["created"], 1)
        reminder = Notification.objects.get(
            related_booking=self.booking,
            notification_type=Notification.CHECK_IN_REMINDER,
        )
        self.assertEqual(reminder.reminder_at, self._aware_today(9, 0))

    def test_same_hour_retry_does_not_duplicate_reminder(self):
        first = create_due_check_in_reminders(now=self._aware_today(10, 5))
        second = create_due_check_in_reminders(now=self._aware_today(10, 40))

        self.assertEqual(first["created"], 1)
        self.assertEqual(second["created"], 0)
        self.assertEqual(
            Notification.objects.filter(
                related_booking=self.booking,
                notification_type=Notification.CHECK_IN_REMINDER,
            ).count(),
            1,
        )

    def test_next_hour_creates_next_reminder(self):
        create_due_check_in_reminders(now=self._aware_today(10, 5))
        result = create_due_check_in_reminders(now=self._aware_today(11, 5))

        self.assertEqual(result["created"], 1)
        self.assertEqual(
            Notification.objects.filter(
                related_booking=self.booking,
                notification_type=Notification.CHECK_IN_REMINDER,
            ).count(),
            2,
        )

    def test_check_in_stops_future_reminders(self):
        create_due_check_in_reminders(now=self._aware_today(10, 5))
        self.booking.checked_in_at = self._aware_today(10, 30)
        self.booking.save(update_fields=["checked_in_at"])

        result = create_due_check_in_reminders(now=self._aware_today(11, 5))

        self.assertEqual(result["created"], 0)
        self.assertEqual(
            Notification.objects.filter(
                related_booking=self.booking,
                notification_type=Notification.CHECK_IN_REMINDER,
            ).count(),
            1,
        )

    def test_expired_unchecked_booking_is_cancelled_not_no_show(self):
        result = create_due_check_in_reminders(now=self._aware_today(15, 1))

        self.assertEqual(result["cancelled"], 1)
        self.booking.refresh_from_db()
        self.ticket.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.CANCELLED)
        self.assertEqual(self.ticket.status, QueueTicket.CANCELLED)
        self.assertIsNone(self.booking.checked_in_at)

    def test_no_reminder_before_six_hour_window(self):
        result = create_due_check_in_reminders(now=self._aware_today(8, 59))

        self.assertEqual(result["created"], 0)
        self.assertFalse(
            Notification.objects.filter(
                related_booking=self.booking,
                notification_type=Notification.CHECK_IN_REMINDER,
            ).exists()
        )

from django.contrib.auth.models import User
from django.db import models


class Notification(models.Model):
    GENERAL = "general"
    QUEUE_UPDATE = "queue_update"
    DISRUPTION = "disruption"
    RESCHEDULE = "reschedule"
    CHECK_IN_REMINDER = "check_in_reminder"

    NOTIFICATION_TYPE = [
        (GENERAL, "General"),
        (QUEUE_UPDATE, "Queue Update"),
        (DISRUPTION, "Disruption"),
        (RESCHEDULE, "Reschedule"),
        (CHECK_IN_REMINDER, "Check-in Reminder"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    title = models.CharField(max_length=100)
    message = models.TextField(blank=True)
    notification_type = models.CharField(
        max_length=100,
        choices=NOTIFICATION_TYPE,
        default=GENERAL,
    )
    related_ticket = models.ForeignKey(
        "queues.QueueTicket",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    related_impact = models.ForeignKey(
        "queues.QueueDisruptionImpact",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    related_booking = models.ForeignKey(
        "bookings.Booking",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )

    # For scheduled check-in reminders, reminder_at identifies the exact hourly
    # reminder slot. The unique constraint prevents duplicate reminders when an
    # hourly scheduler retries the same work.
    reminder_at = models.DateTimeField(null=True, blank=True)

    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["related_booking", "reminder_at"],
                condition=models.Q(
                    notification_type="check_in_reminder",
                    related_booking__isnull=False,
                    reminder_at__isnull=False,
                ),
                name="unique_booking_check_in_reminder_slot",
            )
        ]

    def __str__(self):
        return f"{self.user.username} - {self.title}"

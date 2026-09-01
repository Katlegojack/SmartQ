from django.conf import settings
from django.db import models
from django.utils import timezone


class QueueTicket(models.Model):
    GENERAL = "general"
    PRIORITY = "priority"

    QUEUE_TYPES = [
        (GENERAL, "General"),
        (PRIORITY, "Priority"),
    ]

    # SCHEDULED means the booking exists but the customer has not yet checked in.
    SCHEDULED = "scheduled"
    WAITING = "waiting"
    SERVING = "serving"
    COMPLETED = "completed"
    NO_SHOW = "no_show"
    CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (SCHEDULED, "Scheduled"),
        (WAITING, "Waiting"),
        (SERVING, "Serving"),
        (COMPLETED, "Completed"),
        (NO_SHOW, "No Show"),
        (CANCELLED, "Cancelled"),
    ]

    booking = models.OneToOneField(
        "bookings.Booking",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    assigned_counter = models.ForeignKey(
        "counters.Counter",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    queue_number = models.CharField(max_length=10)
    queue_type = models.CharField(max_length=20, choices=QUEUE_TYPES, default=GENERAL)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=SCHEDULED)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.queue_number


class QueueNumberSequence(models.Model):
    """
    Database-backed allocator for queue numbers.

    One row owns the last number allocated for a specific branch, appointment
    date and queue type. PostgreSQL can lock this small row while allocating the
    next number, preventing concurrent requests from reading the same "latest"
    ticket and generating duplicates.
    """

    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.CASCADE,
        related_name="queue_number_sequences",
    )
    booking_date = models.DateField()
    queue_type = models.CharField(max_length=20, choices=QueueTicket.QUEUE_TYPES)
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["branch", "booking_date", "queue_type"],
                name="unique_queue_number_sequence",
            )
        ]
        ordering = ["branch_id", "booking_date", "queue_type"]

    def __str__(self):
        return (
            f"{self.branch_id}:{self.booking_date}:{self.queue_type}="
            f"{self.last_number}"
        )


class QueueEvent(models.Model):
    """Append-only operational history for queue, booking and counter transitions."""

    TICKET_SCHEDULED = "ticket_scheduled"
    CHECKED_IN = "checked_in"
    CALLED = "called"
    COMPLETED = "completed"
    NO_SHOW = "no_show"
    CANCELLED = "cancelled"
    RESCHEDULED = "rescheduled"
    DISRUPTION_RESCHEDULED = "disruption_rescheduled"
    COUNTER_OPENED = "counter_opened"
    COUNTER_PAUSED = "counter_paused"
    COUNTER_RESUMED = "counter_resumed"
    COUNTER_CLOSED = "counter_closed"
    COUNTER_STAFF_ASSIGNED = "counter_staff_assigned"
    COUNTER_STAFF_UNASSIGNED = "counter_staff_unassigned"

    EVENT_TYPES = [
        (TICKET_SCHEDULED, "Ticket Scheduled"),
        (CHECKED_IN, "Checked In"),
        (CALLED, "Called"),
        (COMPLETED, "Completed"),
        (NO_SHOW, "No Show"),
        (CANCELLED, "Cancelled"),
        (RESCHEDULED, "Rescheduled"),
        (DISRUPTION_RESCHEDULED, "Disruption Rescheduled"),
        (COUNTER_OPENED, "Counter Opened"),
        (COUNTER_PAUSED, "Counter Paused"),
        (COUNTER_RESUMED, "Counter Resumed"),
        (COUNTER_CLOSED, "Counter Closed"),
        (COUNTER_STAFF_ASSIGNED, "Counter Staff Assigned"),
        (COUNTER_STAFF_UNASSIGNED, "Counter Staff Unassigned"),
    ]

    SYSTEM = "system"
    CUSTOMER = "customer"
    STAFF = "staff"
    SOURCES = [
        (SYSTEM, "System"),
        (CUSTOMER, "Customer"),
        (STAFF, "Staff"),
    ]

    ticket = models.ForeignKey(
        "queues.QueueTicket",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
    )
    booking = models.ForeignKey(
        "bookings.Booking",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="queue_events",
    )
    counter = models.ForeignKey(
        "counters.Counter",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="queue_events",
    )
    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="queue_events",
    )
    service = models.ForeignKey(
        "services.Service",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="queue_events",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="queue_events_created",
    )

    event_type = models.CharField(max_length=40, choices=EVENT_TYPES)
    source = models.CharField(max_length=20, choices=SOURCES, default=SYSTEM)
    actor_username = models.CharField(max_length=150, blank=True)
    actor_role = models.CharField(max_length=40, blank=True)

    from_ticket_status = models.CharField(max_length=20, blank=True)
    to_ticket_status = models.CharField(max_length=20, blank=True)
    from_booking_status = models.CharField(max_length=20, blank=True)
    to_booking_status = models.CharField(max_length=20, blank=True)

    queue_number = models.CharField(max_length=10, blank=True)
    queue_type = models.CharField(max_length=20, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["occurred_at", "id"]
        indexes = [
            models.Index(fields=["branch", "occurred_at"], name="queue_evt_branch_time"),
            models.Index(fields=["booking", "occurred_at"], name="queue_evt_booking_time"),
            models.Index(fields=["ticket", "occurred_at"], name="queue_evt_ticket_time"),
            models.Index(fields=["counter", "occurred_at"], name="queue_evt_counter_time"),
            models.Index(fields=["event_type", "occurred_at"], name="queue_evt_type_time"),
        ]

    def __str__(self):
        subject = self.queue_number or f"counter:{self.counter_id}" or "system"
        return f"{self.event_type} - {subject} - {self.occurred_at}"


class QueuePause(models.Model):
    branch = models.ForeignKey("branches.branch", on_delete=models.CASCADE)
    service = models.ForeignKey("services.service", on_delete=models.CASCADE)
    booking_date = models.DateField()
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)
    reason = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.branch} - {self.service} - {self.booking_date}"


class QueueDisruptionImpact(models.Model):
    AFFECTED = "affected"
    RESCHEDULE_RISK = "reschedule_risk"

    IMPACT_TYPES = [
        (AFFECTED, "Affected"),
        (RESCHEDULE_RISK, "Reschedule Risk"),
    ]

    queue_pause = models.ForeignKey("queues.QueuePause", on_delete=models.CASCADE)
    ticket = models.ForeignKey("queues.QueueTicket", on_delete=models.CASCADE)
    impact_type = models.CharField(max_length=35, choices=IMPACT_TYPES)
    message = models.TextField(blank=True)
    is_notified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("queue_pause", "ticket", "impact_type")

    def __str__(self):
        return f"{self.ticket.queue_number} - {self.impact_type}"

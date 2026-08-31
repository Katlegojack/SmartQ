from django.conf import settings
from django.db import models

from branches.models import Branch
from queues.models import QueueTicket


class Counter(models.Model):
    """Physical/service counter and its current operational state."""

    OPEN = "open"
    CLOSED = "closed"
    PAUSED = "paused"

    STATUS_CHOICES = [
        (OPEN, "Open"),
        (CLOSED, "Closed"),
        (PAUSED, "Paused"),
    ]

    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name="counters",
    )
    counter_number = models.CharField(max_length=20)
    queue_type = models.CharField(
        max_length=20,
        choices=QueueTicket.QUEUE_TYPES,
        default=QueueTicket.GENERAL,
    )

    # OneToOne enforces the approved Day 33 rule that one staff member can be
    # assigned to at most one counter at a time. Role/branch compatibility is
    # validated by the counter assignment service before this field is changed.
    assigned_staff = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_counter",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=CLOSED,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_staffed(self):
        """Return True when a Counter Staff user is assigned to this counter."""
        return self.assigned_staff_id is not None

    def __str__(self):
        return f"{self.branch.branch_code} - Counter {self.counter_number}"

from django.contrib.auth.models import User
from django.db import models

from branches.models import Branch
from services.models import Service


class Booking(models.Model):
    """Customer appointment record and service lifecycle state."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"

    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (CONFIRMED, "Confirmed"),
        (COMPLETED, "Completed"),
        (CANCELLED, "Cancelled"),
        (NO_SHOW, "No Show"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT)
    service = models.ForeignKey(Service, on_delete=models.PROTECT)

    booking_date = models.DateField()
    booking_time = models.TimeField()
    is_pregnant = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)

    # A booking exists before the customer arrives. checked_in_at is the explicit
    # boundary between a scheduled appointment and an active live-queue customer.
    checked_in_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_checked_in(self):
        """Return True once the customer has entered the live queue."""
        return self.checked_in_at is not None

    def __str__(self):
        return f"{self.user.username} - {self.branch.branch_code} - {self.service.name}"

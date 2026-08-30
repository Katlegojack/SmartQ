from django.contrib.auth.models import User
from django.db import models

from accounts.models import Profile
from branches.models import Branch
from services.models import Service


class GuestCustomer(models.Model):
    """
    Lightweight identity for a reception-created walk-in.

    A guest walk-in does not need a Django/Smart Q account. We still capture the
    minimum queue-domain information required to identify the person at reception
    and apply the same priority rules used for registered customers.
    """

    full_name = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=30, blank=True)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=20, choices=Profile.GENDER_CHOICE)
    disability_status = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.full_name


class Booking(models.Model):
    """Appointment/walk-in record and service lifecycle state."""

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

    ONLINE = "online"
    WALK_IN = "walk_in"

    SOURCE_CHOICES = [
        (ONLINE, "Online"),
        (WALK_IN, "Walk-in"),
    ]

    # A booking belongs either to a registered Smart Q user or to a guest
    # customer created by reception. The database constraint below prevents a
    # booking from having both identities or neither identity.
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    guest_customer = models.ForeignKey(
        GuestCustomer,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="bookings",
    )

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT)
    service = models.ForeignKey(Service, on_delete=models.PROTECT)

    booking_date = models.DateField()
    booking_time = models.TimeField()
    is_pregnant = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=ONLINE)

    # checked_in_at is the exact time the booking was activated into the live
    # queue. Activation may happen online or in person; it is not proof that the
    # customer is physically inside the branch.
    checked_in_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(user__isnull=False, guest_customer__isnull=True)
                    | models.Q(user__isnull=True, guest_customer__isnull=False)
                ),
                name="booking_has_exactly_one_customer_identity",
            )
        ]

    @property
    def is_checked_in(self):
        """Return True once this booking has entered the live queue."""
        return self.checked_in_at is not None

    @property
    def customer_display_name(self):
        """Return a safe display name for registered or guest customers."""
        if self.user_id:
            full_name = self.user.get_full_name().strip()
            return full_name or self.user.username
        if self.guest_customer_id:
            return self.guest_customer.full_name
        return "Unknown customer"

    def __str__(self):
        return f"{self.customer_display_name} - {self.branch.branch_code} - {self.service.name}"

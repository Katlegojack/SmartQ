from django.core.validators import MinValueValidator
from django.db import models

from branches.models import Branch


class Service(models.Model):
    """Service type that Smart Q can offer across one or more branches."""

    service_code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField()
    average_service_time = models.IntegerField()

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.service_code} - {self.name}"


class BranchService(models.Model):
    """
    Configure whether a branch offers a service and how many online bookings
    that branch can accept for each generated appointment slot.

    Slot duration is intentionally not duplicated here. Smart Q uses the linked
    Service.average_service_time as the approved slot length.
    """

    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name="service_mappings",
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name="branch_mappings",
    )
    max_bookings_per_slot = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["branch", "service"],
                name="unique_branch_service_mapping",
            )
        ]
        ordering = ["branch__name", "service__name"]

    def __str__(self):
        return (
            f"{self.branch.branch_code} - {self.service.service_code} "
            f"({self.max_bookings_per_slot}/slot)"
        )

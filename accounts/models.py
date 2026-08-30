from django.contrib.auth.models import User
from django.db import models


class Profile(models.Model):
    """
    Store Smart Q-specific information for a Django user.

    Django's User model continues to own authentication credentials. Profile owns
    queue-domain information such as priority attributes, the user's Smart Q role,
    and (for branch staff) the branch they are allowed to operate.
    """

    MALE = "male"
    FEMALE = "female"
    OTHER = "other"

    GENDER_CHOICE = [
        (MALE, "Male"),
        (FEMALE, "Female"),
        (OTHER, "Other"),
    ]

    CUSTOMER = "customer"
    RECEPTIONIST = "receptionist"
    COUNTER_STAFF = "counter_staff"
    BRANCH_MANAGER = "branch_manager"
    SYSTEM_ADMIN = "system_admin"

    ROLE_CHOICES = [
        (CUSTOMER, "Customer"),
        (RECEPTIONIST, "Receptionist"),
        (COUNTER_STAFF, "Counter Staff"),
        (BRANCH_MANAGER, "Branch Manager"),
        (SYSTEM_ADMIN, "System Administrator"),
    ]

    STAFF_ROLES = {
        RECEPTIONIST,
        COUNTER_STAFF,
        BRANCH_MANAGER,
        SYSTEM_ADMIN,
    }

    BRANCH_SCOPED_ROLES = {
        RECEPTIONIST,
        COUNTER_STAFF,
        BRANCH_MANAGER,
    }

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=20, choices=GENDER_CHOICE)
    disability_status = models.BooleanField(default=False)

    # Customer is the safe default for existing and newly-created profiles.
    # Public registration never accepts a caller-supplied staff role.
    role = models.CharField(
        max_length=30,
        choices=ROLE_CHOICES,
        default=CUSTOMER,
    )

    # Receptionist, Counter Staff, and Branch Manager are scoped to one branch.
    # Customers and SYSTEM_ADMIN remain branchless in the current MVP.
    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="staff_profiles",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        role__in=["receptionist", "counter_staff", "branch_manager"],
                        branch__isnull=False,
                    )
                    | models.Q(
                        role__in=["customer", "system_admin"],
                        branch__isnull=True,
                    )
                ),
                name="profile_role_has_valid_branch_scope",
            )
        ]

    @property
    def is_smartq_staff(self):
        """Return True when the profile belongs to an operational Smart Q role."""
        return self.role in self.STAFF_ROLES

    @property
    def is_system_admin(self):
        """System administrators are not restricted to one branch."""
        return self.role == self.SYSTEM_ADMIN

    def __str__(self):
        return f"{self.user.username} ({self.role})"

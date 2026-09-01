from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers

from branches.models import Branch

from .models import Profile


MANAGED_STAFF_ROLES = [
    Profile.RECEPTIONIST,
    Profile.COUNTER_STAFF,
    Profile.BRANCH_MANAGER,
    Profile.SYSTEM_ADMIN,
]

BRANCH_SCOPED_STAFF_ROLES = [
    Profile.RECEPTIONIST,
    Profile.COUNTER_STAFF,
    Profile.BRANCH_MANAGER,
]


class AccountSerializer(serializers.ModelSerializer):
    """Read-only representation of the authenticated Smart Q account."""

    role = serializers.CharField(source="profile.role", read_only=True)
    branch_id = serializers.SerializerMethodField()
    branch_name = serializers.SerializerMethodField()
    date_of_birth = serializers.DateField(source="profile.date_of_birth", read_only=True)
    gender = serializers.CharField(source="profile.gender", read_only=True)
    disability_status = serializers.BooleanField(
        source="profile.disability_status",
        read_only=True,
    )

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "role",
            "branch_id",
            "branch_name",
            "date_of_birth",
            "gender",
            "disability_status",
        ]
        read_only_fields = fields

    def get_branch_id(self, obj):
        return obj.profile.branch_id

    def get_branch_name(self, obj):
        return obj.profile.branch.name if obj.profile.branch else None


class CustomerRegistrationSerializer(serializers.Serializer):
    """
    Validate public customer registration.

    The public endpoint intentionally does NOT expose `role`, `branch`, `is_staff`,
    or `is_superuser`. A caller must never be able to register themselves as staff.
    """

    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    date_of_birth = serializers.DateField()
    gender = serializers.ChoiceField(choices=Profile.GENDER_CHOICE)
    disability_status = serializers.BooleanField(default=False)

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("A user with this username already exists.")
        return value

    def validate_password(self, value):
        # Reuse Django's configured password validators rather than duplicating
        # password policy inside Smart Q.
        validate_password(value)
        return value

    @transaction.atomic
    def create(self, validated_data):
        """Create User + Profile as one database transaction."""
        user = User.objects.create_user(
            username=validated_data["username"],
            password=validated_data["password"],
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
            email=validated_data.get("email", ""),
        )

        Profile.objects.create(
            user=user,
            date_of_birth=validated_data["date_of_birth"],
            gender=validated_data["gender"],
            disability_status=validated_data.get("disability_status", False),
            role=Profile.CUSTOMER,
            branch=None,
        )

        return user


class StaffAccountSerializer(serializers.ModelSerializer):
    """Read-only System Admin representation of an operational staff account."""

    role = serializers.CharField(source="profile.role", read_only=True)
    branch_id = serializers.IntegerField(source="profile.branch_id", read_only=True)
    branch_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "role",
            "branch_id",
            "branch_name",
            "is_active",
            "date_joined",
        ]
        read_only_fields = fields

    def get_branch_name(self, obj):
        return obj.profile.branch.name if obj.profile.branch else None


def validate_staff_role_branch(role, branch):
    """
    Enforce the same role/branch invariant as the Profile database constraint.

    Receptionist, Counter Staff and Branch Manager are branch-scoped.
    System Admin is intentionally global and therefore branchless.
    """
    if role in BRANCH_SCOPED_STAFF_ROLES and branch is None:
        raise serializers.ValidationError(
            {"branch": "This staff role must be assigned to an active branch."}
        )

    if role == Profile.SYSTEM_ADMIN and branch is not None:
        raise serializers.ValidationError(
            {"branch": "A System Admin must not be assigned to a branch."}
        )


class StaffAccountCreateSerializer(serializers.Serializer):
    """Validate System Admin creation of Smart Q operational staff accounts."""

    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    date_of_birth = serializers.DateField()
    gender = serializers.ChoiceField(choices=Profile.GENDER_CHOICE)
    disability_status = serializers.BooleanField(default=False)
    role = serializers.ChoiceField(choices=MANAGED_STAFF_ROLES)
    branch = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("A user with this username already exists.")
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate(self, attrs):
        validate_staff_role_branch(attrs["role"], attrs.get("branch"))
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        profile_data = {
            "date_of_birth": validated_data.pop("date_of_birth"),
            "gender": validated_data.pop("gender"),
            "disability_status": validated_data.pop("disability_status", False),
            "role": validated_data.pop("role"),
            "branch": validated_data.pop("branch", None),
        }

        user = User.objects.create_user(**validated_data)
        Profile.objects.create(user=user, **profile_data)
        return user


class StaffAccountUpdateSerializer(serializers.Serializer):
    """Validate safe partial updates to an existing Smart Q staff account."""

    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    date_of_birth = serializers.DateField(required=False)
    gender = serializers.ChoiceField(choices=Profile.GENDER_CHOICE, required=False)
    disability_status = serializers.BooleanField(required=False)
    role = serializers.ChoiceField(choices=MANAGED_STAFF_ROLES, required=False)
    branch = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )

    def validate(self, attrs):
        profile = self.instance.profile
        role = attrs.get("role", profile.role)
        branch = attrs.get("branch", profile.branch)
        validate_staff_role_branch(role, branch)
        return attrs

    @transaction.atomic
    def update(self, instance, validated_data):
        profile = instance.profile

        for field in ["first_name", "last_name", "email"]:
            if field in validated_data:
                setattr(instance, field, validated_data[field])

        user_fields = [
            field
            for field in ["first_name", "last_name", "email"]
            if field in validated_data
        ]
        if user_fields:
            instance.save(update_fields=user_fields)

        for field in [
            "date_of_birth",
            "gender",
            "disability_status",
            "role",
            "branch",
        ]:
            if field in validated_data:
                setattr(profile, field, validated_data[field])

        profile_fields = [
            field
            for field in [
                "date_of_birth",
                "gender",
                "disability_status",
                "role",
                "branch",
            ]
            if field in validated_data
        ]
        if profile_fields:
            profile.save(update_fields=profile_fields)

        return instance

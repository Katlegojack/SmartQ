from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers

from .models import Profile


class AccountSerializer(serializers.ModelSerializer):
    """Read-only representation of the authenticated Smart Q account."""

    role = serializers.CharField(source="profile.role", read_only=True)
    branch_id = serializers.IntegerField(source="profile.branch_id", read_only=True)
    branch_name = serializers.CharField(source="profile.branch.name", read_only=True)
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

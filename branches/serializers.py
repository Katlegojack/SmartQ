from rest_framework import serializers

from .models import Branch


class BranchSerializer(serializers.ModelSerializer):
    """Public read-only branch catalogue representation."""

    class Meta:
        model = Branch
        fields = [
            "id",
            "branch_code",
            "name",
            "address",
            "city",
            "opening_time",
            "closing_time",
            "is_active",
            "created_at",
        ]
        read_only_fields = fields


class BranchAdminSerializer(serializers.ModelSerializer):
    """System Admin serializer for branch creation and configuration changes."""

    class Meta:
        model = Branch
        fields = [
            "id",
            "branch_code",
            "name",
            "address",
            "city",
            "opening_time",
            "closing_time",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        opening_time = attrs.get(
            "opening_time",
            getattr(self.instance, "opening_time", None),
        )
        closing_time = attrs.get(
            "closing_time",
            getattr(self.instance, "closing_time", None),
        )

        if opening_time is not None and closing_time is not None:
            if opening_time >= closing_time:
                raise serializers.ValidationError(
                    {"closing_time": "Closing time must be later than opening time."}
                )

        return attrs

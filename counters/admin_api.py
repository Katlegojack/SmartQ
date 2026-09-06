from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsSystemAdmin
from branches.models import Branch
from queues.models import QueueTicket

from .models import Counter
from .serializers import CounterSerializer
from .services import get_current_ticket


class CounterAdminWriteSerializer(serializers.Serializer):
    """Validate System Admin counter configuration without exposing live state."""

    branch = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.filter(is_active=True),
        required=False,
    )
    counter_number = serializers.CharField(max_length=20)
    queue_type = serializers.ChoiceField(choices=QueueTicket.QUEUE_TYPES)

    def validate(self, attrs):
        instance = self.instance
        branch = attrs.get("branch", instance.branch if instance else None)
        counter_number = attrs.get(
            "counter_number",
            instance.counter_number if instance else "",
        ).strip()

        if not branch:
            raise serializers.ValidationError({"branch": "Select an active branch."})
        if not counter_number:
            raise serializers.ValidationError({"counter_number": "Counter number is required."})

        duplicate = Counter.objects.filter(
            branch=branch,
            counter_number__iexact=counter_number,
        )
        if instance:
            duplicate = duplicate.exclude(pk=instance.pk)
        if duplicate.exists():
            raise serializers.ValidationError(
                {"counter_number": "That counter number already exists in this branch."}
            )

        attrs["counter_number"] = counter_number
        return attrs

    def create(self, validated_data):
        return Counter.objects.create(
            branch=validated_data["branch"],
            counter_number=validated_data["counter_number"],
            queue_type=validated_data["queue_type"],
            status=Counter.CLOSED,
        )

    def update(self, instance, validated_data):
        # Counter identity stays in its original branch. Moving a physical
        # counter across branches would make its historical queue events lie.
        instance.counter_number = validated_data.get(
            "counter_number", instance.counter_number
        )
        instance.queue_type = validated_data.get("queue_type", instance.queue_type)
        instance.save(update_fields=["counter_number", "queue_type"])
        return instance


class CounterAdminListCreateAPIView(APIView):
    """List and create physical counters from the System Admin control plane."""

    permission_classes = [IsSystemAdmin]

    def get(self, request):
        counters = (
            Counter.objects.select_related("branch", "assigned_staff")
            .order_by("branch__name", "counter_number", "id")
        )
        return Response(CounterSerializer(counters, many=True).data)

    def post(self, request):
        serializer = CounterAdminWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        counter = serializer.save()
        return Response(
            CounterSerializer(counter).data,
            status=status.HTTP_201_CREATED,
        )


class CounterAdminDetailAPIView(APIView):
    """Update safe counter configuration while preserving operational history."""

    permission_classes = [IsSystemAdmin]

    def get_object(self, pk):
        return get_object_or_404(
            Counter.objects.select_related("branch", "assigned_staff"),
            pk=pk,
        )

    def get(self, request, pk):
        return Response(CounterSerializer(self.get_object(pk)).data)

    def patch(self, request, pk):
        counter = self.get_object(pk)
        if counter.status != Counter.CLOSED:
            return Response(
                {"detail": "Close this counter before changing its configuration."},
                status=status.HTTP_409_CONFLICT,
            )
        if get_current_ticket(counter) is not None:
            return Response(
                {"detail": "Resolve the current customer before changing this counter."},
                status=status.HTTP_409_CONFLICT,
            )
        if "branch" in request.data and str(request.data.get("branch")) != str(counter.branch_id):
            return Response(
                {"detail": "A counter cannot be moved to another branch. Create a new counter there instead."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = CounterAdminWriteSerializer(
            counter,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        counter = serializer.save()
        return Response(CounterSerializer(counter).data)

from datetime import date

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from branches.models import Branch
from .availability import get_slot_availability
from .models import BranchService, Service
from .serializers import BranchServiceSerializer, ServiceSerializer


class ServiceListAPIView(ListAPIView):
    """Return the global active service catalogue."""

    serializer_class = ServiceSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return Service.objects.filter(is_active=True).order_by("name")


class BranchServiceListAPIView(ListAPIView):
    """Return only active services that a selected active branch offers."""

    serializer_class = BranchServiceSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        branch = get_object_or_404(
            Branch,
            pk=self.kwargs["branch_id"],
            is_active=True,
        )
        return BranchService.objects.filter(
            branch=branch,
            is_active=True,
            service__is_active=True,
        ).select_related("branch", "service").order_by("service__name")


class BranchServiceAvailabilityAPIView(APIView):
    """Return backend-generated appointment slots and remaining capacity."""

    permission_classes = [AllowAny]

    def get(self, request, branch_id, service_id):
        branch = get_object_or_404(Branch, pk=branch_id, is_active=True)
        service = get_object_or_404(Service, pk=service_id, is_active=True)

        mapping = BranchService.objects.filter(
            branch=branch,
            service=service,
            is_active=True,
        ).first()
        if mapping is None:
            return Response(
                {"detail": "This service is not offered at the selected branch."},
                status=status.HTTP_404_NOT_FOUND,
            )

        raw_date = request.query_params.get("date")
        if not raw_date:
            return Response(
                {"detail": "Provide a date query parameter in YYYY-MM-DD format."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            booking_date = date.fromisoformat(raw_date)
        except ValueError:
            return Response(
                {"detail": "Invalid date. Use YYYY-MM-DD format."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        slots = get_slot_availability(branch, service, booking_date)
        return Response(
            {
                "branch": branch.id,
                "service": service.id,
                "date": booking_date,
                "slot_duration_minutes": service.average_service_time,
                "max_bookings_per_slot": mapping.max_bookings_per_slot,
                "slots": slots,
            },
            status=status.HTTP_200_OK,
        )

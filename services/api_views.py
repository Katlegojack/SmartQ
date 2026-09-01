from datetime import date

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsSystemAdmin
from branches.models import Branch

from .availability import get_slot_availability
from .models import BranchService, Service
from .serializers import (
    BranchServiceAdminSerializer,
    BranchServiceSerializer,
    ServiceAdminSerializer,
    ServiceSerializer,
)


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


class ServiceAdminListCreateAPIView(ListAPIView):
    """System Admin global service catalogue including inactive services."""

    serializer_class = ServiceAdminSerializer
    permission_classes = [IsAuthenticated, IsSystemAdmin]

    def get_queryset(self):
        return Service.objects.all().order_by("name")

    def post(self, request):
        serializer = ServiceAdminSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        service = serializer.save()
        return Response(
            ServiceAdminSerializer(service).data,
            status=status.HTTP_201_CREATED,
        )


class ServiceAdminDetailAPIView(APIView):
    """Read or update one service while preserving historical references."""

    permission_classes = [IsAuthenticated, IsSystemAdmin]

    def get_object(self, pk):
        return get_object_or_404(Service, pk=pk)

    def get(self, request, pk):
        return Response(ServiceAdminSerializer(self.get_object(pk)).data)

    def patch(self, request, pk):
        service = self.get_object(pk)
        serializer = ServiceAdminSerializer(
            service,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        service = serializer.save()
        return Response(ServiceAdminSerializer(service).data)


class BranchServiceAdminListCreateAPIView(ListAPIView):
    """System Admin view of all branch/service capacity mappings."""

    serializer_class = BranchServiceAdminSerializer
    permission_classes = [IsAuthenticated, IsSystemAdmin]

    def get_queryset(self):
        return BranchService.objects.select_related("branch", "service").all()

    def post(self, request):
        serializer = BranchServiceAdminSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        mapping = serializer.save()
        return Response(
            BranchServiceAdminSerializer(mapping).data,
            status=status.HTTP_201_CREATED,
        )


class BranchServiceAdminDetailAPIView(APIView):
    """Read or update one branch/service capacity mapping."""

    permission_classes = [IsAuthenticated, IsSystemAdmin]

    def get_object(self, pk):
        return get_object_or_404(
            BranchService.objects.select_related("branch", "service"),
            pk=pk,
        )

    def get(self, request, pk):
        return Response(BranchServiceAdminSerializer(self.get_object(pk)).data)

    def patch(self, request, pk):
        mapping = self.get_object(pk)
        serializer = BranchServiceAdminSerializer(
            mapping,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        mapping = serializer.save()
        return Response(BranchServiceAdminSerializer(mapping).data)

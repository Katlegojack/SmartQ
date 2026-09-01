from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsSystemAdmin

from .models import Branch
from .serializers import BranchAdminSerializer, BranchSerializer


class BranchListAPIView(ListAPIView):
    """Return active branches for public/customer booking flows."""

    serializer_class = BranchSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return Branch.objects.filter(is_active=True).order_by("name")


class BranchAdminListCreateAPIView(ListAPIView):
    """System Admin branch catalogue including inactive branches."""

    serializer_class = BranchAdminSerializer
    permission_classes = [IsAuthenticated, IsSystemAdmin]

    def get_queryset(self):
        return Branch.objects.all().order_by("name")

    def post(self, request):
        serializer = BranchAdminSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        branch = serializer.save()
        return Response(
            BranchAdminSerializer(branch).data,
            status=status.HTTP_201_CREATED,
        )


class BranchAdminDetailAPIView(APIView):
    """Read or update one branch without hard-deleting historical context."""

    permission_classes = [IsAuthenticated, IsSystemAdmin]

    def get_object(self, pk):
        return get_object_or_404(Branch, pk=pk)

    def get(self, request, pk):
        return Response(BranchAdminSerializer(self.get_object(pk)).data)

    def patch(self, request, pk):
        branch = self.get_object(pk)
        serializer = BranchAdminSerializer(
            branch,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        branch = serializer.save()
        return Response(BranchAdminSerializer(branch).data)

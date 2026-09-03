from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Profile
from accounts.permissions import IsBranchManager
from branches.models import Branch


class BranchCounterStaffListAPIView(APIView):
    """Return active Counter Staff visible to an authorised branch manager."""

    permission_classes = [IsBranchManager]

    def get(self, request, branch_id):
        branch = get_object_or_404(Branch, pk=branch_id, is_active=True)
        self.check_object_permissions(request, branch)

        staff = (
            User.objects.filter(
                profile__role=Profile.COUNTER_STAFF,
                profile__branch=branch,
                is_active=True,
            )
            .select_related("profile", "profile__branch", "assigned_counter")
            .order_by("first_name", "last_name", "username", "id")
        )

        return Response(
            [
                {
                    "id": user.id,
                    "username": user.username,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "display_name": user.get_full_name().strip() or user.username,
                    "assigned_counter_id": getattr(user, "assigned_counter", None).id
                    if hasattr(user, "assigned_counter")
                    else None,
                    "assigned_counter_number": getattr(user, "assigned_counter", None).counter_number
                    if hasattr(user, "assigned_counter")
                    else None,
                }
                for user in staff
            ],
            status=status.HTTP_200_OK,
        )

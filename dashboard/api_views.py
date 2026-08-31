from datetime import date

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsBranchManager
from branches.models import Branch
from .services import get_manager_dashboard


def parse_dashboard_date(raw_date):
    """
    Parse an optional YYYY-MM-DD dashboard date.

    Returning a small (value, error) tuple keeps input validation explicit and
    avoids leaking Python ValueError details through the API.
    """
    if not raw_date:
        return timezone.localdate(), None

    try:
        return date.fromisoformat(raw_date), None
    except ValueError:
        return None, "date must use YYYY-MM-DD format."


class BranchManagerDashboardAPIView(APIView):
    """Return the operational dashboard for an authorised branch manager/admin."""

    permission_classes = [IsBranchManager]

    def get(self, request, branch_id):
        branch = get_object_or_404(Branch, pk=branch_id, is_active=True)

        # Role permission answers 'is this a manager/admin?'; object permission
        # answers 'may this specific manager see this specific branch?'.
        self.check_object_permissions(request, branch)

        dashboard_date, error = parse_dashboard_date(
            request.query_params.get("date")
        )
        if error:
            return Response(
                {"detail": error},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            get_manager_dashboard(branch, dashboard_date),
            status=status.HTTP_200_OK,
        )

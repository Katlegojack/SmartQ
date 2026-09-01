from datetime import timedelta

from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsBranchManager
from branches.models import Branch

from .reporting import build_branch_operational_report


MAX_REPORT_DAYS = 366
DEFAULT_REPORT_DAYS = 30


def resolve_report_period(request):
    """Return an inclusive report period or a user-facing validation error."""
    today = timezone.localdate()
    start_raw = request.query_params.get("start_date")
    end_raw = request.query_params.get("end_date")

    end_date = parse_date(end_raw) if end_raw else today
    start_date = (
        parse_date(start_raw)
        if start_raw
        else end_date - timedelta(days=DEFAULT_REPORT_DAYS - 1)
        if end_date
        else None
    )

    if (start_raw and start_date is None) or (end_raw and end_date is None):
        return None, Response(
            {"detail": "start_date and end_date must use YYYY-MM-DD."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if start_date is None or end_date is None:
        return None, Response(
            {"detail": "A valid reporting period is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if start_date > end_date:
        return None, Response(
            {"detail": "start_date cannot be after end_date."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if (end_date - start_date).days + 1 > MAX_REPORT_DAYS:
        return None, Response(
            {"detail": f"Reporting period cannot exceed {MAX_REPORT_DAYS} days."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return (start_date, end_date), None


class BranchOperationalReportAPIView(APIView):
    """Historical QueueEvent report for own-branch Managers and System Admins."""

    permission_classes = [IsBranchManager]

    def get(self, request, branch_id):
        branch = get_object_or_404(Branch, pk=branch_id, is_active=True)
        self.check_object_permissions(request, branch)

        period, error = resolve_report_period(request)
        if error is not None:
            return error

        start_date, end_date = period
        return Response(
            build_branch_operational_report(branch, start_date, end_date),
            status=status.HTTP_200_OK,
        )

"""Reception-specific read contracts used by the Day 51 workflow."""

from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsQueueViewer

from .api_views import get_staff_branch
from .models import Booking
from .serializers import BookingListSerializer


class ReceptionTodayBookingsAPIView(APIView):
    """Return today's non-final bookings for the staff member's authorised branch."""

    permission_classes = [IsQueueViewer]

    def get(self, request):
        branch, error_response = get_staff_branch(request)
        if error_response:
            return error_response

        bookings = (
            Booking.objects.filter(
                branch=branch,
                booking_date=timezone.localdate(),
                status__in=[Booking.PENDING, Booking.CONFIRMED],
            )
            .select_related(
                "branch",
                "service",
                "user",
                "guest_customer",
                "queueticket",
            )
            .order_by("booking_time", "id")
        )
        return Response(BookingListSerializer(bookings, many=True).data)

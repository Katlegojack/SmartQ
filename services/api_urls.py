from django.urls import path

from .api_views import (
    BranchServiceAvailabilityAPIView,
    BranchServiceListAPIView,
    ServiceListAPIView,
)


urlpatterns = [
    # Global service catalogue.
    path("", ServiceListAPIView.as_view(), name="api_service_list"),

    # Services configured for one branch.
    path(
        "branches/<int:branch_id>/",
        BranchServiceListAPIView.as_view(),
        name="api_branch_service_list",
    ),

    # Capacity-aware appointment slots for one branch/service/date.
    path(
        "branches/<int:branch_id>/<int:service_id>/availability/",
        BranchServiceAvailabilityAPIView.as_view(),
        name="api_branch_service_availability",
    ),
]

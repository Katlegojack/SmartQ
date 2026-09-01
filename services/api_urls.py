from django.urls import path

from .api_views import (
    BranchServiceAdminDetailAPIView,
    BranchServiceAdminListCreateAPIView,
    BranchServiceAvailabilityAPIView,
    BranchServiceListAPIView,
    ServiceAdminDetailAPIView,
    ServiceAdminListCreateAPIView,
    ServiceListAPIView,
)


urlpatterns = [
    path("", ServiceListAPIView.as_view(), name="api_service_list"),
    path(
        "branches/<int:branch_id>/",
        BranchServiceListAPIView.as_view(),
        name="api_branch_service_list",
    ),
    path(
        "branches/<int:branch_id>/<int:service_id>/availability/",
        BranchServiceAvailabilityAPIView.as_view(),
        name="api_branch_service_availability",
    ),
    path(
        "admin/",
        ServiceAdminListCreateAPIView.as_view(),
        name="api_admin_service_list_create",
    ),
    path(
        "admin/<int:pk>/",
        ServiceAdminDetailAPIView.as_view(),
        name="api_admin_service_detail",
    ),
    path(
        "admin/branch-services/",
        BranchServiceAdminListCreateAPIView.as_view(),
        name="api_admin_branch_service_list_create",
    ),
    path(
        "admin/branch-services/<int:pk>/",
        BranchServiceAdminDetailAPIView.as_view(),
        name="api_admin_branch_service_detail",
    ),
]

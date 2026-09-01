from django.urls import path

from .api_views import (
    BranchAdminDetailAPIView,
    BranchAdminListCreateAPIView,
    BranchListAPIView,
)


urlpatterns = [
    path("", BranchListAPIView.as_view(), name="api_branch_list"),
    path(
        "admin/",
        BranchAdminListCreateAPIView.as_view(),
        name="api_admin_branch_list_create",
    ),
    path(
        "admin/<int:pk>/",
        BranchAdminDetailAPIView.as_view(),
        name="api_admin_branch_detail",
    ),
]

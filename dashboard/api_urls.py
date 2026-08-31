from django.urls import path

from .api_views import BranchManagerDashboardAPIView


urlpatterns = [
    path(
        "branches/<int:branch_id>/",
        BranchManagerDashboardAPIView.as_view(),
        name="api_branch_manager_dashboard",
    ),
]

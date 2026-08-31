from django.urls import path

from .api_views import (
    BranchCounterListAPIView,
    CounterAssignStaffAPIView,
    CounterCloseAPIView,
    CounterOpenAPIView,
    CounterPauseAPIView,
    CounterResumeAPIView,
    CounterUnassignStaffAPIView,
    MyAssignedCounterAPIView,
)


urlpatterns = [
    path("my/", MyAssignedCounterAPIView.as_view(), name="api_my_assigned_counter"),
    path(
        "branches/<int:branch_id>/",
        BranchCounterListAPIView.as_view(),
        name="api_branch_counter_list",
    ),
    path(
        "<int:counter_id>/assign/",
        CounterAssignStaffAPIView.as_view(),
        name="api_counter_assign_staff",
    ),
    path(
        "<int:counter_id>/unassign/",
        CounterUnassignStaffAPIView.as_view(),
        name="api_counter_unassign_staff",
    ),
    path(
        "<int:counter_id>/open/",
        CounterOpenAPIView.as_view(),
        name="api_counter_open",
    ),
    path(
        "<int:counter_id>/pause/",
        CounterPauseAPIView.as_view(),
        name="api_counter_pause",
    ),
    path(
        "<int:counter_id>/resume/",
        CounterResumeAPIView.as_view(),
        name="api_counter_resume",
    ),
    path(
        "<int:counter_id>/close/",
        CounterCloseAPIView.as_view(),
        name="api_counter_close",
    ),
]

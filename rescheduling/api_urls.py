from django.urls import path

from .api_views import (
    BranchQueuePauseCreateAPIView,
    QueuePauseDetailAPIView,
    QueuePauseResumeAPIView,
)


urlpatterns = [
    path(
        "branches/<int:branch_id>/pauses/",
        BranchQueuePauseCreateAPIView.as_view(),
        name="api_branch_queue_pause_create",
    ),
    path(
        "pauses/<int:pause_id>/",
        QueuePauseDetailAPIView.as_view(),
        name="api_queue_pause_detail",
    ),
    path(
        "pauses/<int:pause_id>/resume/",
        QueuePauseResumeAPIView.as_view(),
        name="api_queue_pause_resume",
    ),
]

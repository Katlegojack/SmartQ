from django.urls import path

from .api_views import (
    BranchQueuePauseCreateAPIView,
    CustomerRescheduleOptionSelectAPIView,
    MyRescheduleRecommendationListAPIView,
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
    path(
        "recommendations/my/",
        MyRescheduleRecommendationListAPIView.as_view(),
        name="api_my_reschedule_recommendations",
    ),
    path(
        "options/<int:option_id>/select/",
        CustomerRescheduleOptionSelectAPIView.as_view(),
        name="api_customer_reschedule_option_select",
    ),
]

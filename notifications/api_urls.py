from django.urls import path #let us define the url routes
#Import the API view that returns the logged-in user's notification
from .api_views import NotificationIsAPIView,UnreadNotificationCountAPIView

# These are the notification API routes.
urlpatterns = [
    #Empty path means this view runs at the parent URL. Ex later: /api/v1/notifications
    path('',NotificationIsAPIView.as_view(),name='api_notification_list'),

    #Return the logged in user's unread notification count. FULL URL: /api/v1/notifications/unread-count
    path('unread-count/',UnreadNotificationCountAPIView.as_view(),name='api_unread_notification_count'),
]
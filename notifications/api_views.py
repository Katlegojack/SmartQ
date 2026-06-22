#DRF generic views help us build common API behaviour quickly
#ListAPIView is used when we want to return a list of objects

from rest_framework.generics import ListAPIView
#Is authenticated means only logged in users can access this API
from rest_framework.permissions import IsAuthenticated

# Import the Notification model so we can query notification records.
from .models import Notification

#Import serializers that convert Notification objects into JSON
from .serializers import NotificationSerializer

class NotificationIsAPIView(ListAPIView):
    #This tells DRF which serializer should convert notifications into JSON
    serializer_class = NotificationSerializer
    #This protects the endpoint, only logged in users should be able to view notifications
    permission_classes =[IsAuthenticated]

    def get_queryset(self):
        #Return notifications of currently logged in users
        #This prevents 1 user from seeing other user's notifications
        return Notification.objects.filter(user=self.request.user)
    

#APIView is used when we want full control over the API response
from rest_framework.views import APIView
#Response let us return custom JSON data
from rest_framework.response import Response
#Import the existing service function so we do not duplicate unread-count logic
from .services import get_unread_notification_count

class UnreadNotificationCountAPIView(APIView):
    #Only logged in users should be able to see their unread notification count
    permission_classes =[IsAuthenticated]

    def get(self,request):
        #Use the existing service function to count unread notifications
        #request.user is the currently logged in user
        unread_count =get_unread_notification_count(request.user)

        #Return a custom JSON response
        return Response(
            {'unread_count':unread_count}
        )
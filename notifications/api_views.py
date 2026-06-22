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
    

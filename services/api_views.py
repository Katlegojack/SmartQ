#ListAPIView is used when the api returns a list of model objects
from rest_framework.generics import ListAPIView
#AllowAny means this endpoint can be accessed without login, Service information is public catalogue data not private customer data
from rest_framework.permissions import AllowAny
#Import service model so we can query service records
from .models import Service
#import serializers that convert service model objects into JSON data
from .serializers import ServiceSerializer

class ServiceListAPIView(ListAPIView):
    #This tells DRF how to convert Service objects into JSON data
    serializer_class = ServiceSerializer
    #ANyone can view  available services
    permission_classes = [AllowAny]

    def get_queryset(self):
        #Only return active services, this prevents inactive services from appearing in the API
        return Service.objects.filter(is_active=True).order_by('name')
    
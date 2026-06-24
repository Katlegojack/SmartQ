#Import DRF serializer tool
#Serializers convert django model objects into JSON-friendly data
from rest_framework import serializers

#Import the service model that we want to expose through the API
from .models import Service

class ServiceSerializer(serializers.ModelSerializer):
    #Meta tells DRF which model this serializer uses and which api fields should be shown in the API responses
    class Meta:
        #This serializer is based on the service model
        model = Service

        #These are the service fields that the API is allowed to return
        fields = ['id','service_code','name','description','average_service_time','is_active','created_at']
        #For now this API is read only, USERS are not allowed to creat/edit services
        read_only_fields =['id','service_code','name','description','average_service_time','is_active','created_at']
        
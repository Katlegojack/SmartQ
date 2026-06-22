from rest_framework import serializers
from .models import Notification

class NotificationSerializer(serializers.ModelSerializer):
    #This serializer controls how Notification object become a JSON data
    class Meta:
        model = Notification #Tell DRF which model this serializer is based on

        #This are the fields we want our api to show
        fields =['id','title','message','notification_type','is_read','created_at']
    
        # For now, this serializer is only for reading notifications.
        # Users should not create notifications directly through this serializer.
        read_only_fields = fields


    
#Import DRF serializer tools
from rest_framework import serializers
#import timezone so we can validate booking dates.
from django.utils import timezone
#Import booking & services models
from .models import Booking
from branches.models import Branch
from services.models import Service

class BookingCreateSerializer(serializers.ModelSerializer):
    #only allow users to choose active branches
    branch = serializers.PrimaryKeyRelatedField(queryset = Branch.objects.filter(is_active=True))
    #only allow users to choose active services
    service = serializers.PrimaryKeyRelatedField(queryset =Service.objects.filter(is_active=True))

    class Meta:
        model = Booking
        #These are the fields an api returns/accepts
        fields = ['id','branch','service','booking_date','booking_time','is_pregnant','status','created_at']
        #The api should not let users manually set these
        read_only_fields = ['id','status','created_at']

        def validate_booking_date(self,value):
            #prevent customers from booking dates in the past
            if value <timezone.now().date():
                raise serializers.ValidationError('Booking cannot be in the past date')
            





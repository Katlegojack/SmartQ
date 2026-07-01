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
            

#This serializer is used when the customer wants to view their own booking
#It gives more readable booking information than the create serializer
class BookingListSerializer(serializers.ModelSerializer):
    #Show the branch name instead of only the branch ID
    branch_name = serializers.CharField(source='branch.name',read_only=True)
    #SHow the service name instead of only the service ID
    service_name = serializers.CharField(source='service.name',read_only=True)

    #Show queue ticket information connected to this booking
    queue_ticket = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        #These are the fields returned when listing the customer's bookings
        fields = ['id','branch','branch_name','service','service_name','booking_date','booking_time','is_pregnant','status','created_at','queue_ticket']

        #This serializer is for reading booking data
        read_only_fields = fields

    def get_queue_ticket(self,obj):
         #SOme bookings may not have queue ticket if something failed earlier, so we handle that safely instead of crashing
        try:
            ticket = obj.queueticket
        except Exception:
            return None
            
        #Return useful queue ticket data to the frontend
        return {
                'id':ticket.id,
                'queue_number':ticket.queue_number,
                'queue_type': ticket.queue_type,
                'status':ticket.status,

            }


class BookingRescheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        #Only these fields can be updated during rescheduling
        fields = ['booking_date','booking_time']

        #Validate that the customer is not choosing a past date
    def validate_booking_date(self,value):
        #Get today's date
        today = timezone.now().date()
        #Prevent customers from selecting a date in the past
        if value <today :
            raise serializers.ValidationError("Booking date cannot be in the past")
            
        return value
        


#Import Django rest framework serializer tools
#Serializers convert QueueTicket model objects into JSON
from rest_framework import serializers
#Import QueueTicket model
from .models import QueueTicket

class QueueTicketSerializer(serializers.ModelSerializer):
    """
    Serializer used to display queue ticket information.

    This serializer is read-only and is primarily used by
    queue operation APIs such as:
    - Call Next
    - Complete Ticket
    - No Show
    - Recall Customer (future)
    """
    #Display related booking ticket information
    booking_id =serializers.IntegerField(source='booking.id',read_only=True)
    
    class Meta:
        model = QueueTicket
        #Fields return by API
        fields = ['id','booking_id','queue_number','queue_type','status','assigned_counter','created_at']
        #This serializer is read only
        read_only_fields = fields
        
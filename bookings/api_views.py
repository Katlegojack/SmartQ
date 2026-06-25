#transaction keeps both -booking +queue ticket creation safe as 1 operation
from django.db import transaction
#CreateAPIView  is used when an api creates 1 model object
from rest_framework.generics import CreateAPIView
#Only logged in users can create a booking
from rest_framework.permissions import IsAuthenticated
#Import the bookingSerializer
from .serializers  import BookingCreateSerializer
#Import QueueTicket so we can check duplicate tickets
from queues.models import QueueTicket
#Import existing queue-ticket creation logic
from queues.services import create_queue_ticket_for_booking

class BookingCreateAPIView(CreateAPIView):
    #This serializer validates and creates booking objects
    serializer_class =BookingCreateSerializer
    #Only logged in users can create booking
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        #SAVE booking and create a queueticket as one safe database operation
        with transaction.atomic():
            #The logged in user becomes the ticket owner
            booking = serializer.save(user=self.request.user)

            #Create a queueticket only if 1 does not exist
            if not QueueTicket.objects.filter(booking=booking).exists():
                create_queue_ticket_for_booking(booking)

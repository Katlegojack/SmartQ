#transaction keeps both -booking +queue ticket creation safe as 1 operation
from django.db import transaction
#CreateAPIView  is used when an api creates 1 model object,ListAPIView is used when an API returns a list of model objects.
from rest_framework.generics import CreateAPIView,ListAPIView
#Only logged in users can create a booking
from rest_framework.permissions import IsAuthenticated
#Import the bookingSerializer,# BookingListSerializer is for showing bookings to the customer.
from .serializers  import BookingCreateSerializer,BookingListSerializer
#Import QueueTicket so we can check duplicate tickets
from queues.models import QueueTicket
#Import existing queue-ticket creation logic
from queues.services import create_queue_ticket_for_booking
# Import the Booking model so we can query booking records.
from .models import Booking

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

class MyBookingListAPIView(ListAPIView):
    #This serializers controls how bookings are shown on the api responses
    serializer_class = BookingListSerializer
    #ONly logged in users can view their bookings
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        #Returns bookings that belongs to the logged in user, this prevents users from seeing other customer's users
        return Booking.objects.filter(user=self.request.user).select_related('branch','service').order_by('-created_at')
    
#transaction keeps both -booking +queue ticket creation safe as 1 operation
from django.db import transaction

#get_object_or_404 helps us safely fetch 1 object or return 404
from django.shortcuts import get_object_or_404

#Response lets return custom API responses, status give us HTTP status codes like 400 or 200
from rest_framework.response import Response
from rest_framework import status

# RetrieveAPIView is used when an API returns one specific model object.
#CreateAPIView  is used when an api creates 1 model object,ListAPIView is used when an API returns a list of model objects.
from rest_framework.generics import CreateAPIView,ListAPIView,RetrieveAPIView

#Only logged in users can create a booking
from rest_framework.permissions import IsAuthenticated

#Import the bookingSerializer,# BookingListSerializer is for showing bookings to the customer.
from .serializers  import BookingCreateSerializer,BookingListSerializer,BookingReschudulerSerializer

#Import QueueTicket so we can check duplicate tickets
from queues.models import QueueTicket

#Import existing queue-ticket creation logic
from queues.services import create_queue_ticket_for_booking,determine_queue_type,generate_queue_number

# Import the Booking model so we can query booking records.
from .models import Booking

#API view let us write custom PATCH endpoint
from rest_framework.views import APIView

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
    
class BookingDetailAPIView(RetrieveAPIView):
    #We can reuse branchListSerializer bcz it already shows: branch & service name & queue ticket data
    serializer_class = BookingListSerializer

    #Only logged in user can view booking details
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        #Return only booking that belongs to the logged-in user. This is the security layer
        #If the user requests /api/v1/bookings/5/ Django will only search inside the user's booking
        #So if booking 5 belongs to someone else, the API will return 404
        return Booking.objects.filter(user=self.request.user).select_related('branch','service')
    

class BookingCancelAPIView(APIView):
    #Only logged-in users
    permission_classes = [IsAuthenticated]
    
    def patch(self,request,pk):
        #find the boooking but only inside the logged in user's bookings
        #This prevents 1 customer from cancelling another customer's bookings
        booking = get_object_or_404(Booking,pk=pk, user=request.user)

        #A completed ticket should not be cancelled,once service is completed, the booking history must stay accurate
        if booking.status == Booking.COMPLETED:
            return Response(
                {'detail':'Completed bookings should not be cancelled'},
                status=status.HTTP_400_BAD_REQUEST
            )
        #A no show booking should not be cancelled by the customer afterwards, A no show means missed booking
        if booking.status == Booking.NO_SHOW:
            return Response(
                {'detail':'No-show bookings cannot be cancelled'},
                status= status.HTTP_400_BAD_REQUEST
            )
        
        #If the booking is already cancelled, return it as it is.
        #This makes the endpoint safe if it is twice
        if booking.status == Booking.CANCELLED:
            serializer = BookingListSerializer(booking)
            return Response(serializer.data,status=status.HTTP_200_OK)
        
        #Cancel the booking
        booking.status = Booking.CANCELLED
        booking.save(update_fields=['status'])

        #Cancel the connected queue ticket if it exists
        try:
            ticket =booking.queueticket
            ticket.status = Booking.CANCELLED
            ticket.save(update_fields=['status'])
        except Exception:
            pass

        #Return the updated booking data
        serializer = BookingListSerializer(booking)
        return Response(serializer.data, status=status.HTTP_200_OK)
            

class BookingRescheduleAPIView(APIView):
    permission_classes = [IsAuthenticated] #Only logged in users
    def patch(self,request,pk):
        #Find the booking only if it belongs to a logged in user
        #This prevents 1 customer from rescheduling another customer's booking
        booking = get_object_or_404(Booking,pk=pk,user=request.user)
        #Completed bookings are part of history and cannot be changed
        if booking.status == Booking.COMPLETED:
            return Response(
                {'detail':'Completed booking cannot be rescheduled'},
                status = status.HTTP_400_BAD_REQUEST
            )
        #CANCELLED BOOKINGS ARE finalised and cannot be reopened
        if booking.status == Booking.CANCELLED:
            return Response(
                {'detail':'Cancelled ticket cannot be rescheduled'},
                status = status.HTTP_400_BAD_REQUESTs
            )
        #Validate new booking date and time
        serializer = BookingReschudulerSerializer(booking,data=request.data,partial=True)
        #Stop immediately if validation fails
        serializer.is_valid(raise_exception=True)
        #Save the validated booking changes
        booking = serializer.save()
        #Return the updated booking
        response_serializer = BookingReschudulerSerializer(booking)
        return Response(response_serializer.data,status=status.HTTP_200_OK)
    
        

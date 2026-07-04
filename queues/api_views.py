#APIView gives us full control over the business flow
from rest_framework.views import APIView
#Response is used to return JSON responses
from rest_framework.response import Response
#HTTP status codes
from rest_framework import status
#Only authenticated users should call the next customers
from rest_framework.permissions import IsAuthenticated
#Retrieve objects safely
from django.shortcuts import get_object_or_404
#Counter models
from counters.models import Counter
#QUeue business logic
from .services import call_next_ticket,complete_current_ticket,mark_current_ticket_no_show
from .serializers import QueueTicketSerializer

class CallNextTicketAPIView(APIView):
    #Calls the next customer for a specific counter
    #Only authenticated users can access this endpoint
    permission_classes = [IsAuthenticated]

    def post(self,request,counter_id):
        #Retrieve the requested counter
        counter = get_object_or_404(Counter,pk=counter_id)

        #Ask the service layer to find the next customer
        ticket = call_next_ticket(counter)
        #No customers waiting.
        if ticket is None:
            return Response(
                {'detail':'No waiting customers found'},
                status= status.HTTP_404_NOT_FOUND
            )
        
        #Convert QueueTicket into JSON
        serializer = QueueTicketSerializer(ticket)
        #Return queue information
        return Response(
            serializer.data,
            status = status.HTTP_200_OK
        )
    
class CompleteCurrentTicketAPIView(APIView):
    #Marks the customer currently being served at a counter as complete
    #Only authenticated users may complete this ticket
    permission_classes = [IsAuthenticated]
    def post(self,request,counter_id):
        #Retrieve the requested counter
        counter = get_object_or_404(Counter,pk=counter_id)
        #Complete the ticket currenlty assigned to this counter
        ticket = complete_current_ticket(counter)
        
        #if the counter is not serving anyone anymore
        if ticket is None:
            return Response(
                {'detail':'This counter is not serving any customer'},
                status=status.HTTP_404_NOT_FOUND
            )
        #Convert the updated ticket into JSON
        serializer =QueueTicketSerializer(ticket)

        #Return the completed ticket
        return Response(serializer.data,status=status.HTTP_200_OK)
    
class NoShowCurrentTicketAPIView(APIView):
    #Marks customer currently being served at a certain counter as no show
    #Only authenticated users
    permission_classes = [IsAuthenticated]

    def post(self,request,counter_id):
        #Retrieve the requested counter
        counter = get_object_or_404(Counter,pk=counter_id)
        #Mark current ticket as no show
        ticket = mark_current_ticket_no_show(counter)
        #If the ticket is serving no one
        if ticket is None:
            return Response(
                {'detail':'This counter is not serving any customer'},
                status=status.HTTP_404_NOT_FOUND
            )
        #Convert the updated ticket into a JSON
        serializer = QueueTicketSerializer(ticket)
        #Return the updated ticket
        return Response(serializer.data,status=status.HTTP_200_OK)
    
        
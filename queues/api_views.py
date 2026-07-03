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
from .services import call_next_ticket
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
    
    
#ListAPIView is used when the api returns a list of model objects.
from rest_framework.generics import ListAPIView
#AllowAny means this endpoint can be accessed without login
#Branch information is public catalogue data not private customer data
from rest_framework.permissions import AllowAny
#import branch model so we can queury branch records
from .models import Branch
#import the serializer that converts Branch objects into JSON-friendly data
from .serializers import BranchSerializer

class BranchListAPIView(ListAPIView):
    #This tells DRF how to convert Branch objects into JSON data
    serializer_class = BranchSerializer
    #anyone can view available branches
    permission_classes = [AllowAny]

    def get_queryset(self):
        #Only return active branches, This prevents inactive branches from appearing in the API
        return Branch.objects.filter(is_active=True).order_by('name')
    
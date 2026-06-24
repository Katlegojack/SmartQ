#Import DRF Serializers tools
#Serializers convert django model objects into JSON-data friendly
from rest_framework import serializers
#Import branch models that we want to expose through the api
from .models import Branch

class BranchSerializer(serializers.ModelSerializer):
    #Meta tells DRF which model this serializer uses and which fields should be shown in the API responses
    class Meta:
        #This serializer is based on the Branch model
        model = Branch

        #These are the branch fields the API is allowed to return
        fields = ['id','branch_code','name','address','city','opening_time','closing_time','is_active','created_at']
        #For now this API is read only, Users should not create/edit branches through this serializers yet
        read_only_fields = ['id','branch_code','name','address','city','opening_time','closing_time','is_active','created_at']


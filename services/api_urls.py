#path lets us define URL routes for this app.
from django.urls import path
#Import the service listAPIView 
from .api_views import ServiceListAPIView

#This are the service api routes
urlpatterns =[
    #Return all active services. FULL URL: /api/v1/services/
    path('',ServiceListAPIView.as_view(),name='api_service_list'),
]
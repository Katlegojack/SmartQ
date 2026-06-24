#path let us define URL route for this app
from django.urls import path
#Import the branch ListAPIView
from .api_views import BranchListAPIView

#These are the branch API routes

urlpatterns =[
    #Return all active branches. FULL URL: /api/v1/branches/
    path('',BranchListAPIView.as_view(),name='api_branch_list'),
]
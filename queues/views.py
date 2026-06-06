from django.shortcuts import render

# Create your views here.
from .models import QueueTicket

def ticket_list(request):
    tickets = QueueTicket.objects.all()

    return render(request,'queues/ticket_list.html',{'tickets':tickets})

from django.contrib import admin

# Register your models here.
from .models import Booking
from queues.models import QueueTicket
from queues.services import create_queue_ticket_for_booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
    
        if not QueueTicket.objects.filter(booking=obj).exists():
            create_queue_ticket_for_booking(obj)

from django.db import models
from bookings.models import Booking

# Create your models here.
class QueueTicket(models.Model):
    GENERAL = 'general'
    PRIORITY = 'priority'

    QUEUE_TYPES =[
        (GENERAL, 'General'),
        (PRIORITY, 'Priority'),
    ]

    WAITING = 'waiting'
    SERVING = 'serving'
    COMPLETED = 'completed'
    NO_SHOW = 'no_show'
    CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (WAITING, 'Waiting'),
        (SERVING, 'Serving'),
        (COMPLETED, 'Completed'),
        (NO_SHOW, 'No Show'),
        (CANCELLED, 'Cancelled'),
    ]

    booking = models.OneToOneField(
    "bookings.Booking",
    on_delete=models.CASCADE,
    null=True,
    blank=True
    )

    queue_number = models.CharField(max_length=10)
    queue_type = models.CharField(max_length=20,choices=QUEUE_TYPES,default=GENERAL)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=WAITING)
    created_at= models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.queue_number
    
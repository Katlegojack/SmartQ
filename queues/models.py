from django.db import models
from bookings.models import Booking
from django.utils import timezone
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

    assigned_counter = models.ForeignKey(
        "counters.Counter",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )


    queue_number = models.CharField(max_length=10)
    queue_type = models.CharField(max_length=20,choices=QUEUE_TYPES,default=GENERAL)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=WAITING)
    created_at= models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.queue_number

class QueuePause(models.Model):
    branch = models.ForeignKey('branches.branch',on_delete=models.CASCADE)
    service = models.ForeignKey('services.service',on_delete=models.CASCADE)
    booking_date =models.DateField()
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True,blank=True)
    reason = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.branch} - {self.service} - {self.booking_date}"

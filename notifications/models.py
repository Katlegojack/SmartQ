from django.db import models

# Create your models here.
from django.contrib.auth.models import User

class Notification(models.Model):
    GENERAL ='general'
    QUEUE_UPDATE = 'queue_update'
    DISRUPTION ='disruption'
    RESCHEDULE ='reschedule'

    NOTIFICATION_TYPE = [
        (GENERAL,'General'),
        (QUEUE_UPDATE,'Queue Update'),
        (DISRUPTION,'Disruption'),
        (RESCHEDULE,'Reschedule'),
    ]
    user = models.ForeignKey(User,on_delete=models.CASCADE,related_name='notifications')
    title = models.CharField(max_length=100)
    message = models.TextField(blank=True)
    notification_type = models.CharField(max_length=100, choices=NOTIFICATION_TYPE, default=GENERAL)
    related_ticket = models.ForeignKey('queues.QueueTicket',on_delete=models.SET_NULL,null=True, blank=True)
    related_impact = models.ForeignKey('queues.QueueDisruptionImpact',on_delete=models.SET_NULL,null=True,blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username}- {self.title}"
    

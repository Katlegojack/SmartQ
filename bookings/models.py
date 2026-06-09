from django.db import models

# Create your models here.
from django.contrib.auth.models import User
from branches.models import Branch
from services.models import Service

class Booking(models.Model):
    PENDING ='pending'
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"

    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (CONFIRMED, "Confirmed"),
        (COMPLETED, "Completed"),
        (CANCELLED, "Cancelled"),
        (NO_SHOW, "No Show"),
    ]

    user = models.ForeignKey(User,on_delete= models.CASCADE)
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT)
    service = models.ForeignKey(Service, on_delete=models.PROTECT)
    
    booking_date = models.DateField()
    booking_time = models.TimeField()
    is_pregnant = models.BooleanField(default =False)
    status = models.CharField(max_length=20,choices=STATUS_CHOICES, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f"{self.user.username} - {self.branch.branch_code} - {self.service.name}"


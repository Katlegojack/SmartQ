from django.db import models

# Create your models here.
class RescheduleRecommendation(models.Model):
    PENDING= 'pending'
    APPROVED='approved'
    REJECTED= 'rejected'
    APPLIED = 'applied'
    CANCELLED ='cancelled'

    STATUS_CHOICES =[
        (PENDING,'Pending'),
        (APPROVED,'Approved'),
        (REJECTED,'Rejected'),
        (APPLIED,'Applied'),
        (CANCELLED,'Cancelled'),
    ]

    booking = models.ForeignKey('bookings.Booking',on_delete=models.CASCADE)
    ticket = models.ForeignKey('queues.QueueTicket',on_delete=models.SET_NULL,null=True,blank=True)
    disruption_impact = models.OneToOneField('queues.QueueDisruptionImpact',on_delete=models.SET_NULL,null=True,blank=True)
    old_booking_date = models.DateField()
    old_booking_time = models.TimeField(null=True,blank=True)
    suggested_booking_date = models.DateField()
    suggested_booking_time = models.TimeField(null=True,blank=True)
    priority_on_reschedule = models.BooleanField(default=True)
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES,default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at =models.DateTimeField(auto_now=True)
    applied_at =models.DateTimeField(null=True,blank=True)
    class Meta:
        ordering = ['-created_at']
    def __str__(self):
        return f"{self.booking.user.username} - {self.old_booking_date} to {self.suggested_booking_date} - {self.status}"
    

class RescheduleOption(models.Model):
    recommendation = models.ForeignKey('rescheduling.RescheduleRecommendation',on_delete=models.CASCADE,related_name='option')
    option_date = models.DateField()
    option_time = models.TextField()
    capacity = models.PositiveIntegerField(default=1)
    booked_count =models.PositiveIntegerField(default=0)
    available_count = models.PositiveIntegerField(default=1)
    is_recommended = models.BooleanField(default=False)
    is_selected = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['option_date','option_time']
        unique_together = ('recommendation','option_date','option_time')
    
    def __str__(self):
         return f"{self.recommendation.booking.user.username} - {self.option_date} - {self.option_time}"


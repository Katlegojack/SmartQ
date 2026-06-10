from django.db import models
from branches.models import Branch
from queues.models import QueueTicket
# Create your models here.

class Counter(models.Model):
    OPEN ='open'
    CLOSED = 'closed'
    PAUSED ='paused'

    STATUS_CHOICES =[
        (OPEN,'Open'),
        (CLOSED,'Closed'),
        (PAUSED,'Paused'),
    ]
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE)
    counter_number = models.CharField(max_length=20)
    queue_type = models.CharField(
        max_length=20,
        choices=QueueTicket.QUEUE_TYPES,
        default=QueueTicket.GENERAL
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES,default=CLOSED)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.branch.branch_code}- Counter {self.counter_number}"
    

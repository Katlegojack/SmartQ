from django.db import models
from django.contrib.auth.models import User

# Create your models here.

class Profile(models.Model):
    MALE ='male'
    FEMALE ='female'
    OTHER = 'other'

    GENDER_CHOICE = [
        (MALE,'Male'),
        (FEMALE,'Female'),
        (OTHER,'Other'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=20, choices=GENDER_CHOICE)
    disability_status = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.username
    
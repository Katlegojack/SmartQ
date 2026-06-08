from django.db import models

# Create your models here.
class Branch(models.Model):
    branch_code =models.CharField(max_length=10,unique=True)
    name = models.CharField(max_length=100)
    address = models.CharField(max_length=265)
    city = models.CharField(max_length=100)

    opening_time = models.TimeField()
    closing_time = models.TimeField()

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.branch_code} - {self.name}"

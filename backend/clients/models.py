# clients/models.py
from django.db import models
from users.models import CustomUser  # Import CustomUser from the users app

class Client(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15, blank=True, null=True)
    cin = models.CharField(max_length=15, blank=True, null=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='clients')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
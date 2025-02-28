# users/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('ADMIN', 'Admin'),
        ('EMPLOYEE', 'Employé'),
        ('ACCOUNTANT', 'Comptable'),
        ('CLIENT', 'Client'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='CLIENT')
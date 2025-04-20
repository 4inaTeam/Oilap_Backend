# users/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator

class CustomUser(AbstractUser):

    USERNAME_FIELD = 'email'  # Change the authentication identifier
    REQUIRED_FIELDS = ['username']  # Remove email from required fields

    username_validator = RegexValidator(
        regex=r'^[a-zA-Z]+$',
        message="Username must contain only letters (no numbers or symbols)."
    )
    
    cin_validator = RegexValidator(
        regex=r'^\d{8}$',
        message="CIN must be exactly 8 numeric digits."
    )
    
    tel_validator = RegexValidator(
        regex=r'^\d{8}$',
        message="Telephone must be exactly 8 numeric digits."
    )

    ROLE_CHOICES = [
        ('ADMIN', 'Admin'),
        ('EMPLOYEE', 'Employee'),
        ('ACCOUNTANT', 'Accountant'),
        ('CLIENT', 'Client'),
    ]
    
    username = models.CharField(
        max_length=150,
        validators=[username_validator],
        error_messages={
            'unique': "A user with that username already exists.",
        },
    )
    email = models.EmailField(unique=True)
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='CLIENT')
    profile_photo = models.ImageField(
        upload_to='profile_photos/',
        default='profile_photos/default.png'
    )
    cin = models.CharField(
        max_length=8,
        unique=True,
        validators=[cin_validator],
        null =False,
        blank=False
    )
    tel = models.CharField(
        max_length=8,
        validators=[tel_validator]
    )
    isActive = models.BooleanField(default=True)
    fcm_token = models.CharField(max_length=255, blank=True, null=True)

class Client(models.Model):
    custom_user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='client_profile'
    )
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_clients'
    )

    def __str__(self):
        return self.custom_user.username
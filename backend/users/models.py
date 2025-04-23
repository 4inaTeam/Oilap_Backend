# users/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _

class CustomUserManager(BaseUserManager):
    def create_user(self, cin, email, password=None, **extra_fields):
        if not cin:
            raise ValueError(_('The CIN must be set'))
        email = self.normalize_email(email)
        user = self.model(cin=cin, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, cin, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', 'ADMIN')

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))

        return self.create_user(cin, email, password, **extra_fields)

class CustomUser(AbstractUser):
    USERNAME_FIELD = 'cin'
    REQUIRED_FIELDS = ['email']
    
    # Remove username from fields
    username = None
    
    objects = CustomUserManager()

    # Keep the rest of your fields
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
    
    email = models.EmailField(unique=True, null=False, blank=False)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='CLIENT')
    profile_photo = models.ImageField(
        upload_to='profile_photos/',
        default='profile_photos/default.png'
    )
    cin = models.CharField(
        max_length=8,
        unique=True,
        validators=[RegexValidator(r'^\d{8}$', "CIN must be exactly 8 numeric digits.")],
        null=False,
        blank=False
    )
    tel = models.CharField(
        max_length=8,
        validators=[tel_validator],
        blank=True,
        null=True
    )
    isActive = models.BooleanField(default=True)
    fcm_token = models.CharField(
        max_length=255, 
        blank=True, 
        null=True,
        verbose_name="FCM Device Token"
    )

    def __str__(self):
        return f"{self.cin} - {self.email}"

# Client model remains the same
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
        return self.custom_user.email
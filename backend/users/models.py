from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _


class CustomUserManager(BaseUserManager):
    def create_user(self, cin, username, email, password=None, **extra_fields):
        if not cin:
            raise ValueError(_('The CIN must be set'))
        if not username:
            raise ValueError(_('The username must be set'))
        email = self.normalize_email(email)
        user = self.model(cin=cin, username=username,
                          email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, cin, username, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', 'ADMIN')

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))

        return self.create_user(cin, username, email, password, **extra_fields)


class CustomUser(AbstractUser):
    username = models.CharField(
        max_length=150,
        unique=False,
        help_text=_(
            'Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.'),
    )

    USERNAME_FIELD = 'cin'
    REQUIRED_FIELDS = ['username', 'email']

    objects = CustomUserManager()

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

    email = models.EmailField(unique=True)
    role = models.CharField(
        max_length=20, choices=ROLE_CHOICES, default='CLIENT')
    profile_photo = models.ImageField(
        upload_to='profile_photos/',
        default='profile_photos/default.png'
    )
    cin = models.CharField(
        max_length=8,
        unique=True,
        validators=[RegexValidator(
            r'^\d{8}$', "CIN must be exactly 8 numeric digits.")],
    )
    tel = models.CharField(
        max_length=8,
        validators=[tel_validator],
        blank=True,
        null=True
    )
    isActive = models.BooleanField(default=True)

    # FCM Token pour les notifications push
    fcm_token = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_("FCM Device Token"),
        help_text=_("Firebase Cloud Messaging token for push notifications")
    )

    # Optionnel : pour gérer plusieurs appareils
    notifications_enabled = models.BooleanField(
        default=True,
        verbose_name=_("Notifications enabled"),
        help_text=_("Whether the user wants to receive push notifications")
    )

    # Timestamp de la dernière mise à jour du token FCM
    fcm_token_updated_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_("FCM Token updated at")
    )

    def __str__(self):
        return self.username

    def update_fcm_token(self, token):
        """Méthode pour mettre à jour le token FCM"""
        from django.utils import timezone

        self.fcm_token = token
        self.fcm_token_updated_at = timezone.now()
        self.save(update_fields=['fcm_token', 'fcm_token_updated_at'])

    def can_receive_notifications(self):
        """Vérifie si l'utilisateur peut recevoir des notifications"""
        return (
            self.notifications_enabled and
            self.fcm_token and
            self.isActive
        )


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


# Modèle optionnel pour gérer plusieurs appareils par utilisateur
class UserDevice(models.Model):
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='devices'
    )
    fcm_token = models.CharField(
        max_length=255,
        unique=True,
        verbose_name=_("FCM Device Token")
    )
    device_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Device Name")
    )
    platform = models.CharField(
        max_length=20,
        choices=[
            ('android', 'Android'),
            ('ios', 'iOS'),
            ('web', 'Web'),
            ('windows', 'Windows')
        ],
        default='android'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'fcm_token']
        verbose_name = _("User Device")
        verbose_name_plural = _("User Devices")

    def __str__(self):
        return f"{self.user.username} - {self.device_name or self.platform}"

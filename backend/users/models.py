from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _
import logging

logger = logging.getLogger(__name__)


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

    # Enhanced FCM token field
    fcm_token = models.TextField(  # Changed from CharField to TextField for longer tokens
        blank=True,
        null=True,
        verbose_name=_("FCM Device Token"),
        help_text=_("Firebase Cloud Messaging token for push notifications")
    )

    # Enhanced notification preferences
    notifications_enabled = models.BooleanField(
        default=True,
        verbose_name=_("Notifications enabled"),
        help_text=_("Whether the user wants to receive notifications")
    )

    push_notifications_enabled = models.BooleanField(
        default=True,
        verbose_name=_("Push notifications enabled"),
        help_text=_("Whether the user wants to receive push notifications")
    )

    email_notifications_enabled = models.BooleanField(
        default=True,
        verbose_name=_("Email notifications enabled"),
        help_text=_("Whether the user wants to receive email notifications")
    )

    sms_notifications_enabled = models.BooleanField(
        default=True,
        verbose_name=_("SMS notifications enabled"),
        help_text=_("Whether the user wants to receive SMS notifications")
    )

    fcm_token_updated_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_("FCM Token updated at")
    )

    def __str__(self):
        return self.username

    def update_fcm_token(self, token):
        """Update FCM token for the user"""
        from django.utils import timezone

        if token and len(token.strip()) >= 10:
            self.fcm_token = token.strip()
            self.fcm_token_updated_at = timezone.now()

            # Auto-enable notifications if user provides a valid token
            if not self.notifications_enabled:
                self.notifications_enabled = True
                logger.info(
                    f"Auto-enabled notifications for user {self.id} after FCM token update")

            if not self.push_notifications_enabled:
                self.push_notifications_enabled = True
                logger.info(
                    f"Auto-enabled push notifications for user {self.id} after FCM token update")

            self.save(update_fields=[
                'fcm_token',
                'fcm_token_updated_at',
                'notifications_enabled',
                'push_notifications_enabled'
            ])
            logger.info(f"Updated FCM token for user {self.id}")
            return True
        else:
            logger.warning(
                f"Invalid FCM token provided for user {self.id}: {len(token.strip() if token else '')} characters")
            return False

    def can_receive_notifications(self):
        """Enhanced check if user can receive notifications"""
        # Log the check for debugging
        logger.debug(f"Checking notifications for user {self.id}:")
        logger.debug(f"  - isActive: {self.isActive}")
        logger.debug(
            f"  - notifications_enabled: {self.notifications_enabled}")
        logger.debug(
            f"  - push_notifications_enabled: {self.push_notifications_enabled}")
        logger.debug(f"  - has fcm_token: {bool(self.fcm_token)}")
        logger.debug(f"  - fcm_token length: {len(self.fcm_token or '')}")

        if not self.isActive:
            logger.info(
                f"User {self.id} cannot receive notifications: user is not active")
            return False

        if not self.notifications_enabled:
            logger.info(
                f"User {self.id} cannot receive notifications: notifications disabled")
            return False

        if not self.push_notifications_enabled:
            logger.info(
                f"User {self.id} cannot receive notifications: push notifications disabled")
            return False

        if not self.fcm_token:
            logger.info(
                f"User {self.id} cannot receive notifications: no FCM token")
            return False

        if len(self.fcm_token.strip()) < 10:
            logger.info(
                f"User {self.id} cannot receive notifications: FCM token too short ({len(self.fcm_token.strip())} chars)")
            return False

        logger.info(
            f"User {self.id} can receive notifications: all checks passed")
        return True

    def can_receive_push_notifications(self):
        """Specific check for push notifications"""
        return self.can_receive_notifications()

    def can_receive_email_notifications(self):
        """Specific check for email notifications"""
        return (
            self.isActive and
            self.notifications_enabled and
            self.email_notifications_enabled and
            self.email
        )

    def can_receive_sms_notifications(self):
        """Specific check for SMS notifications"""
        return (
            self.isActive and
            self.notifications_enabled and
            self.sms_notifications_enabled and
            self.tel
        )

    def enable_all_notifications(self):
        """Helper method to enable all notification types"""
        self.notifications_enabled = True
        self.push_notifications_enabled = True
        self.email_notifications_enabled = True
        self.sms_notifications_enabled = True
        self.save(update_fields=[
            'notifications_enabled',
            'push_notifications_enabled',
            'email_notifications_enabled',
            'sms_notifications_enabled'
        ])
        logger.info(f"Enabled all notifications for user {self.id}")

    def get_notification_debug_info(self):
        """Get debug information about user's notification settings"""
        return {
            'user_id': self.id,
            'username': self.username,
            'email': self.email,
            'tel': self.tel,
            'isActive': self.isActive,
            'notifications_enabled': self.notifications_enabled,
            'push_notifications_enabled': self.push_notifications_enabled,
            'email_notifications_enabled': self.email_notifications_enabled,
            'sms_notifications_enabled': self.sms_notifications_enabled,
            'has_fcm_token': bool(self.fcm_token),
            'fcm_token_length': len(self.fcm_token or ''),
            'fcm_token_updated_at': self.fcm_token_updated_at,
            'can_receive_notifications': self.can_receive_notifications(),
            'can_receive_push': self.can_receive_push_notifications(),
            'can_receive_email': self.can_receive_email_notifications(),
            'can_receive_sms': self.can_receive_sms_notifications(),
        }


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

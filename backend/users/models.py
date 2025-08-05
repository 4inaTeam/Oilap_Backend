from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils import timezone
import re
import logging

logger = logging.getLogger(__name__)


def validate_international_phone(value):
    """
    Validates phone number in international format (+countrycode + number) 
    or legacy 8-digit format for backward compatibility.
    """
    if not value:
        return

    cleaned_value = re.sub(r'[^\d+]', '', value)

    if cleaned_value.startswith('+'):
        if len(cleaned_value) < 10 or len(cleaned_value) > 20:
            raise ValidationError(
                _('International phone number must be between 10-20 digits including country code.')
            )

        if not re.match(r'^\+\d{1,4}\d{6,15}$', cleaned_value):
            raise ValidationError(
                _('Invalid international phone format. Use +countrycode followed by phone number.')
            )

        country_validations = {
            '+216': (12, 12),
            '+33': (13, 13),
            '+1': (12, 12),
            '+44': (13, 13),
            '+39': (13, 13),
            '+34': (12, 12),
            '+212': (13, 13),
            '+213': (13, 13),
            '+20': (13, 13),
        }

        for country_code, (min_len, max_len) in country_validations.items():
            if cleaned_value.startswith(country_code):
                if len(cleaned_value) < min_len or len(cleaned_value) > max_len:
                    phone_digits = len(cleaned_value) - len(country_code)
                    expected_digits = min_len - len(country_code)
                    raise ValidationError(
                        _(f'Phone number for {country_code} must have exactly {expected_digits} digits after country code.')
                    )
                break

    elif re.match(r'^\d{8}$', cleaned_value):
        return

    else:
        raise ValidationError(
            _('Phone number must be either 8 digits (legacy format) or international format (+countrycode + number).')
        )


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

    ROLE_CHOICES = [
        ('ADMIN', 'Admin'),
        ('EMPLOYEE', 'Employee'),
        ('ACCOUNTANT', 'Accountant'),
        ('CLIENT', 'Client'),
    ]

    # Popular Tunisian cities choices
    VILLE_CHOICES = [
        ('Tunis', 'Tunis'),
        ('Sfax', 'Sfax'),
        ('Sousse', 'Sousse'),
        ('Kairouan', 'Kairouan'),
        ('Bizerte', 'Bizerte'),
        ('Gabès', 'Gabès'),
        ('Ariana', 'Ariana'),
        ('Gafsa', 'Gafsa'),
        ('Monastir', 'Monastir'),
        ('Ben Arous', 'Ben Arous'),
        ('Kasserine', 'Kasserine'),
        ('Médenine', 'Médenine'),
        ('Nabeul', 'Nabeul'),
        ('Tataouine', 'Tataouine'),
        ('Béja', 'Béja'),
        ('Jendouba', 'Jendouba'),
        ('Mahdia', 'Mahdia'),
        ('Manouba', 'Manouba'),
        ('Sidi Bouzid', 'Sidi Bouzid'),
        ('Siliana', 'Siliana'),
        ('Tozeur', 'Tozeur'),
        ('Zaghouan', 'Zaghouan'),
        ('Kef', 'Kef'),
        ('Kébili', 'Kébili'),
        ('Other', 'Other'),
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

    # Updated tel field to support international phone numbers
    tel = models.CharField(
        max_length=20,  # Increased from 8 to support international format
        validators=[validate_international_phone],
        blank=True,
        null=True,
        help_text=_(
            "Phone number in international format (+countrycode + number) or 8 digits for legacy format")
    )

    # New ville field with default value
    ville = models.CharField(
        max_length=50,
        choices=VILLE_CHOICES,
        default='Tunis',
        verbose_name=_("City"),
        help_text=_("User's city of residence")
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

    def clean(self):
        """Additional model-level validation"""
        super().clean()

        # Clean phone number by removing spaces and formatting
        if self.tel:
            self.tel = re.sub(r'[^\d+]', '', self.tel)

    def get_formatted_phone(self):
        """
        Returns a nicely formatted phone number for display
        """
        if not self.tel:
            return ""

        # If it's an international number
        if self.tel.startswith('+'):
            # You can add more sophisticated formatting here
            return self.tel

        # If it's a legacy 8-digit number, format as Tunisian
        elif len(self.tel) == 8 and self.tel.isdigit():
            # Format as XX XXX XXX for readability
            return f"{self.tel[:2]} {self.tel[2:5]} {self.tel[5:]}"

        return self.tel

    def get_country_code(self):
        """
        Extract country code from phone number
        """
        if not self.tel or not self.tel.startswith('+'):
            return '+216'  # Default to Tunisia for legacy numbers

        # Extract country code (everything before the main number)
        for code in ['+216', '+33', '+49', '+1', '+44', '+39', '+34', '+212', '+213', '+20']:
            if self.tel.startswith(code):
                return code

        # If no known country code found, extract first 1-4 digits after +
        match = re.match(r'^(\+\d{1,4})', self.tel)
        return match.group(1) if match else '+216'

    def get_phone_without_country_code(self):
        """
        Get phone number without country code
        """
        if not self.tel:
            return ""

        if self.tel.startswith('+'):
            country_code = self.get_country_code()
            return self.tel[len(country_code):]

        return self.tel

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
            'ville': self.ville,
            'formatted_phone': self.get_formatted_phone(),
            'country_code': self.get_country_code(),
            'phone_without_country': self.get_phone_without_country_code(),
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
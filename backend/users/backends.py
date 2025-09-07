from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.conf import settings
from rest_framework import exceptions
import time
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


class SecureAuthBackend(ModelBackend):
    """
    Enhanced authentication backend with security features and email verification
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None

        try:
            user = User.objects.get(cin=username)
        except User.DoesNotExist:
            time.sleep(0.5)
            return None

        if self._is_account_locked(user):
            logger.warning(f'Login attempt on locked account: {user.email}')
            return None

        # Check if account is active
        if not user.isActive:
            logger.warning(f'Login attempt on inactive account: {user.email}')
            return None

        # Verify password
        if user.check_password(password):
            # Check email verification (skip for admins/superusers)
            if not user.isVerified and not user.is_superuser and user.role != 'ADMIN':
                logger.warning(
                    f'Login attempt on unverified account: {user.email}')
                raise exceptions.AuthenticationFailed(
                    'Please verify your email address before logging in. Check your email for verification instructions.'
                )

            self._clear_failed_attempts(user)
            logger.info(f'Successful login for user: {user.email}')
            return user
        else:
            self._record_failed_attempt(user)
            logger.warning(f'Failed login attempt for user: {user.email}')
            return None

    def _is_account_locked(self, user):
        """Check if account is locked due to failed attempts"""
        if not getattr(settings, 'ACCOUNT_LOCKOUT_ENABLED', False):
            return False

        cache_key = f'lockout_{user.id}'
        lockout_data = cache.get(cache_key)

        if lockout_data:
            attempts, lockout_time = lockout_data
            lockout_duration = getattr(
                settings, 'ACCOUNT_LOCKOUT_DURATION', 300)
            if time.time() - lockout_time < lockout_duration:
                return True
            else:
                # Lockout expired, clear it
                cache.delete(cache_key)

        return False

    def _record_failed_attempt(self, user):
        """Record failed login attempt"""
        if not getattr(settings, 'ACCOUNT_LOCKOUT_ENABLED', False):
            return

        cache_key = f'lockout_{user.id}'
        lockout_data = cache.get(cache_key, (0, 0))
        attempts, _ = lockout_data

        attempts += 1
        max_attempts = getattr(settings, 'ACCOUNT_LOCKOUT_ATTEMPTS', 5)
        lockout_duration = getattr(settings, 'ACCOUNT_LOCKOUT_DURATION', 300)

        if attempts >= max_attempts:
            # Lock the account
            cache.set(cache_key, (attempts, time.time()), lockout_duration)
            logger.warning(
                f'Account locked for user: {user.email} after {attempts} failed attempts')
        else:
            # Record attempt without lockout time
            cache.set(cache_key, (attempts, 0), lockout_duration)
            logger.info(
                f'Failed attempt {attempts}/{max_attempts} for user: {user.email}')

        # Also update the user model (if these fields exist)
        from django.utils import timezone
        if hasattr(user, 'failed_login_attempts'):
            user.failed_login_attempts = attempts
            user.save(update_fields=['failed_login_attempts'])

        if hasattr(user, 'last_failed_login'):
            user.last_failed_login = timezone.now()
            user.save(update_fields=['last_failed_login'])

    def _clear_failed_attempts(self, user):
        """Clear failed attempts after successful login"""
        cache_key = f'lockout_{user.id}'
        cache.delete(cache_key)

        # Clear from user model too (if these fields exist)
        fields_to_update = []
        if hasattr(user, 'failed_login_attempts') and user.failed_login_attempts > 0:
            user.failed_login_attempts = 0
            fields_to_update.append('failed_login_attempts')

        if hasattr(user, 'last_failed_login') and user.last_failed_login:
            user.last_failed_login = None
            fields_to_update.append('last_failed_login')

        if fields_to_update:
            user.save(update_fields=fields_to_update)
            logger.info(f'Cleared failed attempts for user: {user.email}')

    def get_lockout_info(self, user):
        """Get lockout information for a user"""
        if not getattr(settings, 'ACCOUNT_LOCKOUT_ENABLED', False):
            return None

        cache_key = f'lockout_{user.id}'
        lockout_data = cache.get(cache_key)

        if lockout_data:
            attempts, lockout_time = lockout_data
            max_attempts = getattr(settings, 'ACCOUNT_LOCKOUT_ATTEMPTS', 5)
            lockout_duration = getattr(
                settings, 'ACCOUNT_LOCKOUT_DURATION', 300)

            if lockout_time > 0:  # Account is locked
                remaining_time = max(
                    0, lockout_duration - (time.time() - lockout_time))
                return {
                    'is_locked': True,
                    'attempts': attempts,
                    'max_attempts': max_attempts,
                    'remaining_lockout_time': int(remaining_time),
                    'lockout_expires_at': lockout_time + lockout_duration
                }
            else:  # Has attempts but not locked yet
                return {
                    'is_locked': False,
                    'attempts': attempts,
                    'max_attempts': max_attempts,
                    'remaining_attempts': max_attempts - attempts
                }

        return {
            'is_locked': False,
            'attempts': 0,
            'max_attempts': getattr(settings, 'ACCOUNT_LOCKOUT_ATTEMPTS', 5),
            'remaining_attempts': getattr(settings, 'ACCOUNT_LOCKOUT_ATTEMPTS', 5)
        }

    def user_can_authenticate(self, user):
        """
        Reject users with is_active=False. Custom user models that don't have
        an `is_active` field are allowed.
        """
        is_active = getattr(user, 'is_active', None)
        isActive = getattr(user, 'isActive', None)

        # Check Django's built-in is_active field
        if is_active is not None and not is_active:
            return False

        # Check custom isActive field
        if isActive is not None and not isActive:
            return False

        # Check email verification for non-admin users
        if not user.is_superuser and user.role != 'ADMIN':
            # Default to True if field doesn't exist
            if not getattr(user, 'isVerified', True):
                return False

        return True

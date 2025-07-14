import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class CustomPasswordValidator:
    """
    Custom password validator with enhanced security requirements
    """

    def validate(self, password, user=None):
        errors = []

        if not re.search(r'[A-Z]', password):
            errors.append(
                _('Password must contain at least one uppercase letter.'))

        if not re.search(r'[a-z]', password):
            errors.append(
                _('Password must contain at least one lowercase letter.'))

        if not re.search(r'\d', password):
            errors.append(_('Password must contain at least one digit.'))

        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append(
                _('Password must contain at least one special character.'))

        if self._has_sequential_chars(password):
            errors.append(
                _('Password must not contain sequential characters (e.g., 123, abc).'))

        if self._has_repeated_chars(password):
            errors.append(
                _('Password must not contain more than 2 repeated characters.'))

        if user and self._contains_user_info(password, user):
            errors.append(_('Password must not contain personal information.'))

        if errors:
            raise ValidationError(errors)

    def _has_sequential_chars(self, password):
        """Check for sequential characters like 123, abc, etc."""
        for i in range(len(password) - 2):
            if (ord(password[i]) == ord(password[i+1]) - 1 == ord(password[i+2]) - 2):
                return True
        return False

    def _has_repeated_chars(self, password):
        """Check for more than 2 repeated characters"""
        for i in range(len(password) - 2):
            if password[i] == password[i+1] == password[i+2]:
                return True
        return False

    def _contains_user_info(self, password, user):
        """Check if password contains user information"""
        password_lower = password.lower()
        user_info = [
            user.username.lower() if user.username else '',
            user.email.lower().split('@')[0] if user.email else '',
            user.cin if hasattr(user, 'cin') and user.cin else '',
        ]

        for info in user_info:
            if info and len(info) > 3 and info in password_lower:
                return True
        return False

    def get_help_text(self):
        return _(
            'Your password must contain at least one uppercase letter, '
            'one lowercase letter, one digit, and one special character. '
            'It should not contain sequential or repeated characters, '
            'and should not include personal information.'
        )

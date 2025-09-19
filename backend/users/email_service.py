from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.urls import reverse
from django.core.exceptions import ValidationError
from .models import EmailVerificationToken
import logging

logger = logging.getLogger(__name__)


class EmailVerificationService:
    @staticmethod
    def send_verification_email(user):
        """Send email verification to newly created user"""
        try:
            # Skip sending verification email for admins/superusers
            if user.is_superuser or user.role == 'ADMIN':
                # Automatically verify admin users
                user.isVerified = True
                user.save(update_fields=['isVerified'])
                logger.info(
                    f"Admin user {user.username} automatically verified, no email sent")
                return True

            # Validate email configuration
            if not settings.EMAIL_HOST_USER:
                logger.error("EMAIL_HOST_USER is not configured")
                return False

            if not settings.EMAIL_HOST_PASSWORD:
                logger.error("EMAIL_HOST_PASSWORD is not configured")
                return False

            # Validate user email
            if not user.email:
                logger.error(f"User {user.username} has no email address")
                return False

            logger.info(
                f"Starting email verification process for user: {user.username} ({user.email})")

            # Create verification token
            token = EmailVerificationToken.objects.create(user=user)
            logger.info(f"Created verification token: {token.token}")

            # Build verification URL
            if settings.USE_ABSOLUTE_URLS and hasattr(settings, 'PRODUCTION_DOMAIN'):
                base_url = settings.PRODUCTION_DOMAIN
            else:
                base_url = "http://localhost:8000"  # Default for development

            verification_url = f"{base_url}/api/auth/verify-email/{token.token}/"
            logger.info(f"Generated verification URL: {verification_url}")

            # Email context
            context = {
                'user': user,
                'verification_url': verification_url,
                'token': str(token.token),
            }

            # Render email templates
            try:
                email_html_message = render_to_string(
                    'verification_email.html', context)
                logger.info("HTML email template rendered successfully")
            except Exception as template_error:
                logger.error(
                    f"Failed to render HTML template: {template_error}")
                # Fallback to plain text only
                email_html_message = None

            email_plaintext_message = f"""
Bonjour {user.username},

Votre compte a été créé avec succès. Pour activer votre compte et vous connecter, veuillez vérifier votre adresse e-mail en cliquant sur le lien ci-dessous :

{verification_url}

Ce lien expire dans 24 heures.

Si vous n'avez pas demandé la création de ce compte, ignorez cet e-mail.

Cordialement,
L'équipe Oilap
            """

            # Send email
            logger.info(
                f"Sending email from {settings.EMAIL_HOST_USER} to {user.email}")

            email = EmailMultiAlternatives(
                subject="Vérifiez votre compte - Oilap",
                body=email_plaintext_message,
                from_email=settings.EMAIL_HOST_USER,
                to=[user.email]
            )

            if email_html_message:
                email.attach_alternative(email_html_message, "text/html")

            # Actually send the email
            email.send()

            logger.info(
                f"Verification email sent successfully to {user.email}")
            return True

        except Exception as e:
            logger.error(
                f"Failed to send verification email to {user.email}: {e}")
            logger.error(f"Exception type: {type(e).__name__}")
            logger.error(f"Exception details: {str(e)}")
            # Re-raise for debugging in development
            if settings.DEBUG:
                raise e
            return False

    @staticmethod
    def resend_verification_email(user):
        """Resend verification email"""
        logger.info(f"Resending verification email for user: {user.username}")

        # Invalidate existing tokens
        old_tokens_count = EmailVerificationToken.objects.filter(
            user=user,
            is_used=False
        ).count()

        EmailVerificationToken.objects.filter(
            user=user,
            is_used=False
        ).update(is_used=True)

        logger.info(f"Invalidated {old_tokens_count} old verification tokens")

        # Send new verification email
        return EmailVerificationService.send_verification_email(user)

    @staticmethod
    def test_email_configuration():
        """Test email configuration - useful for debugging"""
        try:
            from django.core.mail import send_mail

            logger.info("Testing email configuration...")
            logger.info(f"EMAIL_HOST: {settings.EMAIL_HOST}")
            logger.info(f"EMAIL_PORT: {settings.EMAIL_PORT}")
            logger.info(f"EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}")
            logger.info(f"EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}")
            logger.info(
                f"EMAIL_HOST_PASSWORD configured: {bool(settings.EMAIL_HOST_PASSWORD)}")

            # Try to send a test email
            send_mail(
                'Test Email Configuration',
                'This is a test email to verify configuration.',
                settings.EMAIL_HOST_USER,
                [settings.EMAIL_HOST_USER],  # Send to self
                fail_silently=False,
            )

            logger.info("Email configuration test PASSED")
            return True

        except Exception as e:
            logger.error(f"Email configuration test FAILED: {e}")
            return False

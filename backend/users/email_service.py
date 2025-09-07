from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.urls import reverse
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
                logger.info(f"Admin user {user.username} automatically verified, no email sent")
                return True
                
            # Create verification token
            token = EmailVerificationToken.objects.create(user=user)
            
            # Build verification URL
            if settings.USE_ABSOLUTE_URLS and hasattr(settings, 'PRODUCTION_DOMAIN'):
                base_url = settings.PRODUCTION_DOMAIN
            else:
                base_url = "http://localhost:8000"  # Default for development
                
            verification_url = f"{base_url}/api/auth/verify-email/{token.token}/"
            
            # Email context
            context = {
                'user': user,
                'verification_url': verification_url,
                'token': str(token.token),
            }
            
            # Render email templates
            email_html_message = render_to_string('verification_email.html', context)
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
            email = EmailMultiAlternatives(
                subject="Vérifiez votre compte - Oilap",
                body=email_plaintext_message,
                from_email=settings.EMAIL_HOST_USER,
                to=[user.email]
            )
            email.attach_alternative(email_html_message, "text/html")
            email.send()
            
            logger.info(f"Verification email sent to {user.email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send verification email to {user.email}: {e}")
            return False
    
    @staticmethod
    def resend_verification_email(user):
        """Resend verification email"""
        # Invalidate existing tokens
        EmailVerificationToken.objects.filter(
            user=user, 
            is_used=False
        ).update(is_used=True)
        
        # Send new verification email
        return EmailVerificationService.send_verification_email(user)
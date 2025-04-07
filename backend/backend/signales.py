from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django_rest_passwordreset.signals import reset_password_token_created
from django.dispatch import receiver

@receiver(reset_password_token_created)
def password_reset_token_created(sender, instance, reset_password_token, *args, **kwargs):
    context = {
        'token': reset_password_token.key,
    }
    email_html_message = render_to_string('password_reset_email.html', context)
    email_plaintext_message = f"Use the following token to reset your password: {reset_password_token.key}"

    email = EmailMultiAlternatives(
        subject="Password Reset for Your Account",
        body=email_plaintext_message,
        from_email="noreply@yourdomain.com",
        to=[reset_password_token.user.email]
    )
    email.attach_alternative(email_html_message, "text/html")
    email.send()
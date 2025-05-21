import random
from django.dispatch import receiver
from django_rest_passwordreset.signals import reset_password_token_created
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings

@receiver(reset_password_token_created)
def password_reset_token_created(sender, instance, reset_password_token, *args, **kwargs):
    code = f"{random.randint(0, 9999):04d}"

    reset_password_token.key = code
    reset_password_token.save(update_fields=['key'])

    context = {'token': code}
    html = render_to_string('password_reset_email.html', context)
    text = f"Use the following code to reset your password: {code}"

    email = EmailMultiAlternatives(
        subject="Your Password Reset Code",
        body=text,
        from_email=settings.EMAIL_HOST_USER,
        to=[reset_password_token.user.email],
    )
    email.attach_alternative(html, "text/html")
    email.send()

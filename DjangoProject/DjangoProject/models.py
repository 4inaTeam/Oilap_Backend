from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.crypto import get_random_string

class CustomUser(AbstractUser):
    email_verified = models.BooleanField(default=False)

    def generate_verification_token(self):
        return get_random_string(64)

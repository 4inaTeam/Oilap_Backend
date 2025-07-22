from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import IntegrityError
import os


class Command(BaseCommand):
    help = 'Create a superuser if it does not exist'

    def handle(self, *args, **options):
        User = get_user_model()  # This will get your CustomUser model

        # Get values from environment variables
        cin = os.environ.get('DJANGO_SUPERUSER_CIN', '12345678')
        username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'admin123')
        tel = os.environ.get('DJANGO_SUPERUSER_TEL', '+21612345678')

        try:
            # Check if superuser already exists (by CIN since it's the USERNAME_FIELD)
            if not User.objects.filter(cin=cin).exists():
                superuser = User.objects.create_superuser(
                    cin=cin,
                    username=username,
                    email=email,
                    password=password,
                    tel=tel,
                    role='ADMIN'
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Superuser "{username}" (CIN: {cin}) created successfully')
                )
                self.stdout.write(f'Email: {email}')
                self.stdout.write(f'Role: {superuser.role}')
            else:
                existing_user = User.objects.get(cin=cin)
                self.stdout.write(
                    self.style.WARNING(
                        f'Superuser with CIN "{cin}" already exists (username: {existing_user.username})')
                )
        except IntegrityError as e:
            self.stdout.write(
                self.style.ERROR(
                    f'Failed to create superuser due to integrity error: {e}')
            )
            # Try to provide more specific error info
            if User.objects.filter(email=email).exists():
                self.stdout.write(
                    self.style.ERROR(f'Email "{email}" is already in use')
                )
            if User.objects.filter(cin=cin).exists():
                self.stdout.write(
                    self.style.ERROR(f'CIN "{cin}" is already in use')
                )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error creating superuser: {e}')
            )

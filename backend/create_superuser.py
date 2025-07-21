from django.contrib.auth import get_user_model
import os
import django
from django.db import IntegrityError

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()


def create_superuser():
    User = get_user_model()  

    cin = os.environ.get('DJANGO_SUPERUSER_CIN', '12345678')
    username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
    email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')
    password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'admin123')
    tel = os.environ.get('DJANGO_SUPERUSER_TEL', '+21612345678')

    try:
        if not User.objects.filter(cin=cin).exists():
            superuser = User.objects.create_superuser(
                cin=cin,
                username=username,
                email=email,
                password=password,
                tel=tel,
                role='ADMIN'
            )

        else:
            existing_user = User.objects.get(cin=cin)

    except IntegrityError as e:

        if User.objects.filter(email=email).exists():
            print(f'Email "{email}" is already in use')
        if User.objects.filter(cin=cin).exists():
            print(f'CIN "{cin}" is already in use')
    except Exception as e:
        print(f'Error creating superuser: {e}')


if __name__ == '__main__':
    create_superuser()

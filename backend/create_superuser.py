from django.contrib.auth import get_user_model
import os
import django
from django.db import IntegrityError, connection
from django.conf import settings

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()


def verify_database_connection():
    """Verify that we're connecting to the correct database"""
    try:
        # Get database configuration
        db_config = settings.DATABASES['default']

        # Test actual connection
        with connection.cursor() as cursor:
            # Get database server info
            cursor.execute("SELECT version();")
            version = cursor.fetchone()[0]

            # Get current database name
            cursor.execute("SELECT current_database();")
            current_db = cursor.fetchone()[0]

            # Get connection info
            cursor.execute("SELECT inet_server_addr(), inet_server_port();")
            server_info = cursor.fetchone()

        return True

    except Exception as e:
        return False


def create_superuser():
    """Create superuser with environment variables"""
    User = get_user_model()

    # Get environment variables
    cin = os.environ.get('DJANGO_SUPERUSER_CIN', '12345678')
    username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
    email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')
    password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'admin123')
    tel = os.environ.get('DJANGO_SUPERUSER_TEL', '+21612345678')

    try:
        # Check if user already exists
        if User.objects.filter(cin=cin).exists():
            existing_user = User.objects.get(cin=cin)
        else:
            superuser = User.objects.create_superuser(
                cin=cin,
                username=username,
                email=email,
                password=password,
                tel=tel,
                role='ADMIN'
            )

    except IntegrityError as e:
        # Check specific constraint violations
        if User.objects.filter(email=email).exists():
            existing_email_user = User.objects.get(email=email)

        if User.objects.filter(username=username).exists():
            existing_username_user = User.objects.get(username=username)

    except Exception as e:
        pass


def main():
    """Main function to run database verification and superuser creation"""
    # First verify database connection
    if verify_database_connection():
        # Then create superuser
        create_superuser()
        return 0
    else:
        return 1


if __name__ == '__main__':
    exit(main())

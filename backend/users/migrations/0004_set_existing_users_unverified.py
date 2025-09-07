from django.db import migrations


def set_existing_users_unverified(apps, schema_editor):
    """Set all existing users as unverified except admins"""
    CustomUser = apps.get_model('users', 'CustomUser')

    CustomUser.objects.filter(role__in=[
                              'CLIENT', 'EMPLOYEE', 'ACCOUNTANT', 'EXPERT_COMPTABLE']).update(isVerified=True)

    CustomUser.objects.filter(role='ADMIN').update(isVerified=True)


def reverse_set_users_verified(apps, schema_editor):
    """Reverse migration - set all users as verified"""
    CustomUser = apps.get_model('users', 'CustomUser')
    CustomUser.objects.all().update(isVerified=True)


class Migration(migrations.Migration):
    dependencies = [
        ('users', '0003_customuser_isverified_emailverificationtoken'),
    ]

    operations = [
        migrations.RunPython(
            set_existing_users_unverified,
            reverse_set_users_verified,
        ),
    ]

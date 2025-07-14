# Alternative approach - create this as a new migration file
# users/migrations/0006_add_security_fields.py

from django.db import migrations, models
from django.utils import timezone


def set_default_password_changed_at(apps, schema_editor):
    """Set default password_changed_at for existing users"""
    CustomUser = apps.get_model('users', 'CustomUser')
    now = timezone.now()
    for user in CustomUser.objects.all():
        user.password_changed_at = now
        user.save(update_fields=['password_changed_at'])


def reverse_password_changed_at(apps, schema_editor):
    """Reverse operation - no action needed"""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0005_alter_customuser_tel'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='failed_login_attempts',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='customuser',
            name='last_failed_login',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='customuser',
            name='password_history',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='customuser',
            name='password_changed_at',
            field=models.DateTimeField(null=True, blank=True),
        ),
        # Data migration to set default values
        migrations.RunPython(
            set_default_password_changed_at,
            reverse_password_changed_at,
        ),
        # Make the field non-nullable after setting default values
        migrations.AlterField(
            model_name='customuser',
            name='password_changed_at',
            field=models.DateTimeField(default=timezone.now),
        ),
    ]

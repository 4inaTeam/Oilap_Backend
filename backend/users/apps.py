from django.apps import AppConfig

class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'  # Keep this as-is

    def ready(self):
        # Import signals to ensure they're connected
        import users.signals  # Add this line
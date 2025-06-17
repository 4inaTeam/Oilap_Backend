
from django.apps import AppConfig


class FacturesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'factures'
    
    def ready(self):
        # Import signal handlers when the app is ready
        import factures.signals
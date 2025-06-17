# tickets/apps.py
from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)

class TicketsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tickets'

    def ready(self):
        # Initialize Firebase
        from django.conf import settings
        if not hasattr(settings, 'FIREBASE_APP'):
            try:
                from .firebase_service import initialize_firebase
                settings.FIREBASE_APP = initialize_firebase()
            except ImportError as e:
                logger.error(f"Error importing firebase_service: {str(e)}")
        
        # Import signals
        try:
            import tickets.signals
        except ImportError as e:
            logger.error(f"Error importing tickets signals: {str(e)}")
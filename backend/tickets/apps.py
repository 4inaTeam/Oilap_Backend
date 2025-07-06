from django.apps import AppConfig
import logging
import threading
import time

logger = logging.getLogger(__name__)


class TicketsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tickets'

    def ready(self):
        self._initialize_firebase()

        self._import_signals()

        self._test_firebase_connection_async()

    def _initialize_firebase(self):
        """Initialize Firebase app if not already initialized"""
        from django.conf import settings

        if not hasattr(settings, 'FIREBASE_APP'):
            try:
                from .firebase_service import initialize_firebase
                settings.FIREBASE_APP = initialize_firebase()
                logger.info("Firebase initialized successfully")
            except ImportError as e:
                logger.error(f"Error importing firebase_service: {str(e)}")
            except Exception as e:
                logger.error(f"Error initializing Firebase: {str(e)}")

    def _import_signals(self):
        """Safely import signals"""
        try:
            import tickets.signals
            logger.info("Tickets signals imported successfully")
        except ImportError as e:
            logger.error(f"Error importing tickets signals: {str(e)}")

    def _test_firebase_connection_async(self):
        """Test Firebase connection in a separate thread to avoid blocking startup"""
        def test_connection():
            time.sleep(2)

            max_retries = 3
            for attempt in range(max_retries):
                try:
                    from firebase_admin import firestore
                    db = firestore.client()
                    db.collection('test_ping').document(
                        'ping').set({'pong': True})
                    logger.info("Firebase connection test successful")
                    return
                except Exception as e:
                    logger.warning(
                        f"Firebase connection test failed (attempt {attempt + 1}): {str(e)}")
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)

            logger.error("Firebase connection test failed after all retries")

        thread = threading.Thread(target=test_connection, daemon=True)
        thread.start()

import firebase_admin
from firebase_admin import credentials
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def initialize_firebase():
    try:
        # Check if already initialized
        if firebase_admin._apps:
            return firebase_admin.get_app()
            
        # Get credentials path from settings
        cred_path = getattr(settings, 'FIREBASE_CREDENTIAL_PATH', None)
        if not cred_path:
            logger.error("FIREBASE_CREDENTIAL_PATH not set in settings")
            return None
            
        # Initialize Firebase
        cred = credentials.Certificate(cred_path)
        app = firebase_admin.initialize_app(cred)
        return app
    except Exception as e:
        logger.error(f"Error initializing Firebase: {str(e)}")
        return None
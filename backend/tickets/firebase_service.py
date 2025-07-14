import firebase_admin
from firebase_admin import credentials, messaging
import os
import json
import logging

logger = logging.getLogger(__name__)


def initialize_firebase():

    if firebase_admin._apps:
        return firebase_admin.get_app()

    try:
        # Method 1: Try environment variable first (recommended)
        firebase_creds_json = os.getenv('FIREBASE_CREDENTIALS_JSON')

        if firebase_creds_json:
            try:
                cred_dict = json.loads(firebase_creds_json)
                cred = credentials.Certificate(cred_dict)
                logger.info(
                    "Using Firebase credentials from environment variable")
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in FIREBASE_CREDENTIALS_JSON: {e}")
                return None
        else:
            # Method 2: Try file path
            cred_path = os.getenv(
                'FIREBASE_CREDENTIALS_PATH', 'firebase/serviceAccountKey.json')

            # Make sure path is absolute
            if not os.path.isabs(cred_path):
                from django.conf import settings
                cred_path = os.path.join(settings.BASE_DIR, cred_path)

            if os.path.exists(cred_path):
                try:
                    cred = credentials.Certificate(cred_path)
                    logger.info(
                        f"Using Firebase credentials from file: {cred_path}")
                except Exception as e:
                    logger.error(f"Failed to load credentials from file: {e}")
                    return None
            else:
                logger.error(
                    f"Firebase credentials file not found: {cred_path}")
                return None

        # Initialize Firebase
        app = firebase_admin.initialize_app(cred)
        logger.info("Firebase initialized successfully")
        return app

    except Exception as e:
        logger.error(f"Error initializing Firebase: {e}")
        return None


def send_push_notification(fcm_token, title, body, data=None):
    """Send push notification via Firebase"""
    try:
        # Ensure Firebase is initialized
        if not firebase_admin._apps:
            initialize_firebase()

        if not firebase_admin._apps:
            logger.error("Cannot send notification: Firebase not initialized")
            return False

        # Create message
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body
            ),
            data=data or {},
            token=fcm_token
        )

        # Send message
        response = messaging.send(message)
        logger.info(f"Push notification sent successfully: {response}")
        return True

    except messaging.UnregisteredError:
        logger.warning(f"FCM token is unregistered: {fcm_token}")
        return False
    except messaging.InvalidArgumentError as e:
        logger.error(f"Invalid argument for push notification: {e}")
        return False
    except Exception as e:
        logger.error(f"Error sending push notification: {e}")
        return False

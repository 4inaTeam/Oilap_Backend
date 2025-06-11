from django.conf import settings
from twilio.rest import Client
import logging

logger = logging.getLogger(__name__)

class TwilioService:
    def __init__(self):
        try:
            self.client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        except Exception as e:
            logger.error(f"Twilio init failed: {e}")
            self.client = None

    def send_sms(self, to_number, message_body):
        if not self.client or not to_number:
            return False
            
        try:
            message = self.client.messages.create(
                body=message_body,
                from_=settings.TWILIO_PHONE_NUMBER,
                to=to_number
            )
            logger.info(f"SMS sent to {to_number}: {message.sid}")
            return True
        except Exception as e:
            logger.error(f"SMS failed: {str(e)}")
            return False
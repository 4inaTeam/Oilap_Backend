from django.conf import settings
from twilio.rest import Client
import logging

logger = logging.getLogger(__name__)

class TwilioService:
    def __init__(self):
        self.client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

    def send_sms(self, to_number, message_body):
        try:
            message = self.client.messages.create(
                body=message_body,
                from_=settings.TWILIO_PHONE_NUMBER,
                to=to_number
            )
            logger.info(f"SMS sent to {to_number}: {message.sid}")
            return True
        except Exception as e:
            logger.error(f"Failed to send SMS to {to_number}: {str(e)}")
            return False
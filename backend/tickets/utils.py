# tickets/utils.py
import requests
from django.conf import settings
from django.core.mail import send_mail
from twilio.rest import Client
from firebase_admin import messaging
import logging
from firebase_admin import firestore

logger = logging.getLogger(__name__)

def send_email_notification(user, facture):
    try:
        subject = f"New Facture Created: {facture.facture_number}"
        message = f"Hello {user.username},\n\nYour facture {facture.facture_number} has been created. Amount: {facture.final_total} TND."
        
        send_mail(
            subject,
            message,
            settings.EMAIL_HOST_USER,
            [user.email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        return False

def send_sms_notification(user, facture):
    try:
        if not user.tel:
            return False
            
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        message = client.messages.create(
            body=f"New facture {facture.facture_number} created. Amount: {facture.final_total} TND",
            from_=settings.TWILIO_PHONE_NUMBER,
            to=f"+216{user.tel}"  # Tunisian prefix
        )
        return True
    except Exception as e:
        logger.error(f"Error sending SMS: {str(e)}")
        return False

def send_push_notification(user, facture):
    try:
        if not user.fcm_token:
            return False

        # Send notification
        message = messaging.Message(
            notification=messaging.Notification(
                title="New Facture Created",
                body=f"Facture {facture.facture_number} - {facture.final_total} TND",
            ),
            token=user.fcm_token,
            data={
                "type": "facture",
                "id": str(facture.id),
                "route": "/facture_detail"
            }
        )
        response = messaging.send(message)
        
        # Log to Firestore
        db = firestore.client()
        doc_ref = db.collection('notifications').document()
        doc_ref.set({
            'user_id': str(user.id),
            'user_email': user.email,
            'facture_id': str(facture.id),
            'facture_number': facture.facture_number,
            'title': "New Facture Created",
            'body': f"Facture {facture.facture_number} - {facture.final_total} TND",
            'fcm_token': user.fcm_token,
            'sent_at': firestore.SERVER_TIMESTAMP,
            'status': 'success',
            'message_id': response,
            'ticket_type': 'PUSH'
        })
        
        return True
    except Exception as e:
        logger.error(f"Error sending push notification: {str(e)}")
        
        # Log error to Firestore
        db = firestore.client()
        db.collection('notification_errors').document().set({
            'error': str(e),
            'user_id': str(user.id) if user else None,
            'facture_id': str(facture.id) if facture else None,
            'timestamp': firestore.SERVER_TIMESTAMP
        })
        
        return False
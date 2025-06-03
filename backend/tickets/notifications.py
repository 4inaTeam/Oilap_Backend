from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from .sms import TwilioService
import logging
from firebase_admin import firestore

logger = logging.getLogger(__name__)

def _get_notification_context(ticket):
    """Helper method to get common notification context"""
    return {
        'client_name': ticket.client.get_full_name(),
        'ticket_date': ticket.date.strftime("%Y-%m-%d %H:%M"),
        'facture_amount': f"{ticket.facture.total_amount:.2f}€",
        'due_date': ticket.facture.due_date.strftime("%Y-%m-%d"),
        'product_id': ticket.product.id
    }
def _log_notification_to_firebase(ticket, notification_type, status, error=None):
    try:
        db = firestore.client()
        recipient = ticket.client.email if notification_type == 'email' else ticket.client.phone_number
        context = _get_notification_context(ticket)
        
        notification_data = {
            'type': notification_type,
            'status': status,
            'timestamp': firestore.SERVER_TIMESTAMP,
            'recipient': recipient,
            'ticket_id': ticket.id,
            'error': error,
            'details': {
                'product_id': context['product_id'],
                'facture_amount': context['facture_amount'],
                'due_date': context['due_date']
            }
        }
        db.collection('notifications').add(notification_data)
    except Exception as e:
        logger.error(f"Firebase logging failed: {e}")

def send_email_notification(ticket):
    status = 'failed'
    error = None
    try:
        context = _get_notification_context(ticket)
        subject = f"Ticket créé pour le produit {context['product_id']}"
        message = render_to_string('emails/ticket_notification.txt', context)
        html_message = render_to_string('emails/ticket_notification.html', context)
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [ticket.client.email],
            html_message=html_message,
            fail_silently=False
        )
        status = 'success'
    except Exception as e:
        logger.error(f"Email failed: {e}")
        error = str(e)
    finally:
        _log_notification_to_firebase(ticket, 'email', status, error)
    return status == 'success'

def send_sms_notification(ticket):
    if not settings.TWILIO_ENABLED:
        _log_notification_to_firebase(ticket, 'sms', 'disabled', "SMS disabled")
        return False
    
    status = 'failed'
    error = None
    try:
        context = _get_notification_context(ticket)
        sms_body = render_to_string('sms/ticket_notification.txt', context)
        
        twilio_service = TwilioService()
        if twilio_service.send_sms(ticket.client.phone_number, sms_body):
            status = 'success'
    except Exception as e:
        logger.error(f"SMS failed: {e}")
        error = str(e)
    finally:
        _log_notification_to_firebase(ticket, 'sms', status, error)
    return status == 'success'
import logging
from django.core.mail import send_mail, EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
from .sms import TwilioService
from firebase_admin import firestore
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def _get_notification_context(ticket):
    """Safe context generation matching your actual model structure"""
    try:
        # Calculate a due date (30 days from facture creation)
        calculated_due_date = ticket.facture.created_at + timedelta(days=30)
        
        # Get product quality display name
        product_quality = ticket.product.get_quality_display() if ticket.product.quality else 'N/A'
        
        return {
            'client_name': ticket.client.get_full_name() or ticket.client.username,
            'product_name': f'Produit #{ticket.product.id}',  # Since Product has no name field
            'product_id': ticket.product.id,
            'product_quality': product_quality,
            'product_quantity': ticket.product.quantity,
            'ticket_date': ticket.date,
            'facture_number': ticket.facture.facture_number,
            'facture_amount': ticket.facture.final_total,
            'due_date': calculated_due_date,
            'payment_status': ticket.facture.get_payment_status_display(),
        }
    except Exception as e:
        logger.error(f"Context generation error: {e}")
        # Fallback context with safe defaults
        return {
            'client_name': getattr(ticket.client, 'username', 'Client'),
            'product_name': f'Produit #{getattr(ticket.product, "id", "N/A")}',
            'product_id': getattr(ticket.product, 'id', 'N/A'),
            'product_quality': 'N/A',
            'product_quantity': 1,
            'ticket_date': getattr(ticket, 'date', datetime.now()),
            'facture_number': getattr(ticket.facture, 'facture_number', 'N/A') if hasattr(ticket, 'facture') else 'N/A',
            'facture_amount': 0,
            'due_date': datetime.now() + timedelta(days=30),
            'payment_status': 'Unpaid',
        }

def send_email_notification(ticket):
    status = 'failed'
    error = None
    
    try:
        # Check if client has email
        if not ticket.client.email:
            logger.warning(f"No email address for client {ticket.client.username}")
            return False
            
        logger.info(f"Attempting to send email to {ticket.client.email} for ticket {ticket.id}")
        
        context = _get_notification_context(ticket)
        logger.debug(f"Email context: {context}")
        
        subject = f"Ticket créé - Facture {context.get('facture_number', '')}"
        
        # Render templates with proper error handling
        try:
            message = render_to_string('emails/ticket_notification.txt', context)
            logger.debug("Plain text template rendered successfully")
        except Exception as template_error:
            logger.error(f"Failed to render text template: {template_error}")
            # Fallback message
            message = f"""
Bonjour {context.get('client_name', '')},

Votre ticket pour {context.get('product_name', '')} a été généré avec succès.

Détails :
- Facture : {context.get('facture_number', '')}
- Produit : {context.get('product_name', '')} (Qualité: {context.get('product_quality', '')})
- Quantité : {context.get('product_quantity', 1)}
- Date de création : {context.get('ticket_date', '').strftime('%d/%m/%Y') if context.get('ticket_date') else 'N/A'}
- Montant total : {context.get('facture_amount', 0)} €
- Date d'échéance : {context.get('due_date', '').strftime('%d/%m/%Y') if context.get('due_date') else 'N/A'}
- Statut : {context.get('payment_status', 'Unpaid')}

Cordialement,
L'équipe Ollap
            """.strip()
        
        try:
            html_message = render_to_string('emails/ticket_notification.html', context)
            logger.debug("HTML template rendered successfully")
        except Exception as template_error:
            logger.error(f"Failed to render HTML template: {template_error}")
            html_message = None
        
        # Send email
        if html_message:
            # Send HTML email
            email = EmailMessage(
                subject=subject,
                body=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[ticket.client.email],
            )
            email.content_subtype = "html"
            email.send(fail_silently=False)
            logger.info("HTML email sent successfully")
        else:
            # Send plain text email
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[ticket.client.email],
                fail_silently=False,
            )
            logger.info("Plain text email sent successfully")
        
        status = 'success'
        logger.info(f"Email sent successfully to {ticket.client.email} for ticket {ticket.id}")
        
    except Exception as e:
        logger.error(f"Email sending failed for ticket {ticket.id}: {e}", exc_info=True)
        error = str(e)
        
    finally:
        try:
            _log_notification_to_firebase(ticket, 'email', status, error)
        except Exception as firebase_error:
            logger.error(f"Firebase log failed: {firebase_error}")
    
    return status == 'success'

def _log_notification_to_firebase(ticket, notification_type, status, error=None):
    """Log notification attempt to Firebase"""
    try:
        db = firestore.client()
        doc_ref = db.collection('notifications').document()
        doc_ref.set({
            'ticket_id': ticket.id,
            'client_id': ticket.client.id,
            'product_id': ticket.product.id,
            'facture_id': ticket.facture.id,
            'facture_number': ticket.facture.facture_number,
            'type': notification_type,
            'status': status,
            'error': error,
            'timestamp': firestore.SERVER_TIMESTAMP
        })
        logger.debug(f"Logged {notification_type} notification to Firebase: {status}")
    except Exception as e:
        logger.error(f"Firebase logging failed: {e}")

def send_sms_notification(ticket):
    if not getattr(settings, 'TWILIO_ENABLED', False):
        logger.warning("SMS notifications disabled")
        return False
        
    status = 'failed'
    error = None
    
    try:
        if not ticket.client.tel:
            logger.warning(f"No phone number for client {ticket.client.username}")
            return False
            
        context = _get_notification_context(ticket)
        
        try:
            sms_body = render_to_string('emails/ticket_notification.txt', context)
        except Exception as template_error:
            logger.error(f"Failed to render SMS template: {template_error}")
            # Fallback SMS message
            sms_body = f"Bonjour {context.get('client_name', '')}, votre ticket pour {context.get('product_name', '')} a été créé. Facture: {context.get('facture_number', '')} - Montant: {context.get('facture_amount', 0)}€"
        
        twilio_service = TwilioService()
        if twilio_service.send_sms(ticket.client.tel, sms_body):
            status = 'success'
            logger.info(f"SMS sent to {ticket.client.tel}")
            
    except Exception as e:
        logger.error(f"SMS failed: {e}", exc_info=True)
        error = str(e)
        
    finally:
        try:
            _log_notification_to_firebase(ticket, 'sms', status, error)
        except Exception as firebase_error:
            logger.error(f"Firebase log failed: {firebase_error}")
    
    return status == 'success'
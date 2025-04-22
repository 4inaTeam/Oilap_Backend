from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def send_ticket_notification(ticket):
    try:
        context = {
            'client_name': ticket.client.get_full_name(),
            'ticket_date': ticket.date,
            'facture_amount': ticket.facture.total_amount,
            'due_date': ticket.facture.due_date
        }
        
        subject = f"Ticket créé pour le produit {ticket.product.id}"
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
    except Exception as e:
        logger.error(f"Failed to send ticket notification: {e}")
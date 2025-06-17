# tickets/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from factures.models import Facture
from .models import Ticket
from .utils import send_email_notification, send_sms_notification, send_push_notification
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Facture)
def create_facture_notification(sender, instance, created, **kwargs):
    if created:
        user = instance.client
        notification_types = ['EMAIL', 'PUSH']  # Default notifications
        
        # Add SMS if phone exists
        if user.tel:
            notification_types.append('SMS')

        for n_type in notification_types:
            try:
                # Create ticket record
                ticket = Ticket.objects.create(
                    user=user,
                    facture=instance,
                    message=f"New facture {instance.facture_number} created",
                    ticket_type=n_type
                )
                
                # Send notification
                success = False
                if n_type == 'EMAIL':
                    success = send_email_notification(user, instance)
                elif n_type == 'SMS':
                    success = send_sms_notification(user, instance)
                elif n_type == 'PUSH':
                    success = send_push_notification(user, instance)
                
                # Update ticket status
                if success:
                    ticket.is_sent = True
                    ticket.sent_at = timezone.now()
                    ticket.save()
            except Exception as e:
                logger.error(f"Error processing {n_type} notification: {str(e)}")
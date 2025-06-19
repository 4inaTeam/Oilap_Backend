from django.db.models.signals import post_save
from django.dispatch import receiver
from factures.models import Facture
from .models import Ticket, Notification
from .utils import send_email_notification, send_sms_notification, send_push_notification
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Facture)
def create_facture_notification(sender, instance, created, **kwargs):
    """
    Signal handler to create notifications when a new facture is created.
    This creates both Ticket records (for tracking) and Notification records (for the app).
    """
    if created:
        user = instance.client
        notification_types = ['EMAIL', 'PUSH']
        
        if user.tel:
            notification_types.append('SMS')

        # Create Notification record first (for the app)
        try:
            notification = Notification.create_facture_notification(user, instance)
            logger.info(f"Created notification record for user {user.id}, facture {instance.facture_number}")
        except Exception as e:
            logger.error(f"Error creating notification record: {str(e)}")

        # Create Ticket records and send notifications
        for n_type in notification_types:
            try:
                ticket = Ticket.objects.create(
                    user=user,
                    facture=instance,
                    message=f"New facture {instance.facture_number} created",
                    ticket_type=n_type
                )
                
                success = False
                if n_type == 'EMAIL':
                    success = send_email_notification(user, instance)
                elif n_type == 'SMS':
                    success = send_sms_notification(user, instance)
                elif n_type == 'PUSH':
                    success = send_push_notification(user, instance)
                
                if success:
                    ticket.is_sent = True
                    ticket.sent_at = timezone.now()
                    ticket.save()
                    logger.info(f"Successfully sent {n_type} notification for facture {instance.facture_number}")
                else:
                    logger.warning(f"Failed to send {n_type} notification for facture {instance.facture_number}")
                    
            except Exception as e:
                logger.error(f"Error processing {n_type} notification: {str(e)}")
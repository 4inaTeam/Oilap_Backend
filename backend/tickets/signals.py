from django.db.models.signals import post_save
from django.dispatch import receiver
from products.models import Product
from factures.models import Facture
from .models import Ticket, Notification
from .utils import send_email_notification, send_email_notification_for_product, send_push_notification_for_product, send_sms_notification, send_push_notification, send_sms_notification_for_product
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Product)
def create_product_ready_notification(sender, instance, created, **kwargs):
    """
    Signal handler to create notifications when a product is done and added to facture.
    This is triggered by the existing product status change logic.
    """
    # Only send notification when product status changes to 'done' and it's added to a facture
    if not created and instance.status == 'done' and instance.facture and instance.payement == 'unpaid':
        user = instance.client
        facture = instance.facture

        # Check if we already sent a notification for this product
        existing_notification = Notification.objects.filter(
            user=user,
            product=instance,
            type='product_ready'
        ).exists()

        if existing_notification:
            logger.info(
                f"Notification already exists for product {instance.id}")
            return

        notification_types = ['EMAIL', 'PUSH']

        if user.tel:
            notification_types.append('SMS')

        # Create Notification record first (for the app)
        try:
            notification = Notification.create_product_ready_notification(
                user, instance, facture)
            logger.info(
                f"Created product ready notification for user {user.id}, product {instance.id}, facture {facture.facture_number}")
        except Exception as e:
            logger.error(
                f"Error creating product ready notification: {str(e)}")

        # Create Ticket records and send notifications
        for n_type in notification_types:
            try:
                ticket = Ticket.objects.create(
                    user=user,
                    facture=facture,
                    product=instance,
                    message=f"Your product (Quality: {instance.get_quality_display()}) is ready! Added to facture {facture.facture_number}. Please visit accounting office to pay {facture.final_total} TND.",
                    ticket_type=n_type
                )

                success = False
                if n_type == 'EMAIL':
                    success = send_email_notification_for_product(
                        user, instance, facture)
                elif n_type == 'SMS':
                    success = send_sms_notification_for_product(
                        user, instance, facture)
                elif n_type == 'PUSH':
                    success = send_push_notification_for_product(
                        user, instance, facture)

                if success:
                    ticket.is_sent = True
                    ticket.sent_at = timezone.now()
                    ticket.save()
                    logger.info(
                        f"Successfully sent {n_type} notification for product {instance.id}")
                else:
                    logger.warning(
                        f"Failed to send {n_type} notification for product {instance.id}")

            except Exception as e:
                logger.error(
                    f"Error processing {n_type} notification: {str(e)}")


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
            notification = Notification.create_facture_notification(
                user, instance)
            logger.info(
                f"Created notification record for user {user.id}, facture {instance.facture_number}")
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
                    logger.info(
                        f"Successfully sent {n_type} notification for facture {instance.facture_number}")
                else:
                    logger.warning(
                        f"Failed to send {n_type} notification for facture {instance.facture_number}")

            except Exception as e:
                logger.error(
                    f"Error processing {n_type} notification: {str(e)}")

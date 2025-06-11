import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from factures.models import Facture
from .models import Ticket
from .notifications import send_email_notification, send_sms_notification

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Facture)
def create_tickets_for_facture(sender, instance, created, **kwargs):
    """Create tickets for all products in a facture when facture is created"""
    if not created:
        return
        
    try:
        # Get all products linked to this facture
        products = instance.products.all()
        
        for product in products:
            # Create ticket for each product
            ticket = Ticket.objects.create(
                product=product,
                client=instance.client,
                facture=instance
            )
            logger.info(f"Created Ticket {ticket.id} for Product {product.id} in Facture {instance.facture_number}")
            
        logger.info(f"Created {products.count()} tickets for Facture {instance.facture_number}")
        
    except Exception as e:
        logger.error(f"Ticket creation failed for Facture {instance.facture_number}: {str(e)}")

@receiver(post_save, sender=Ticket)
def handle_ticket_notifications(sender, instance, created, **kwargs):
    """Send notifications when a ticket is created"""
    if not created:
        return

    logger.info(f"Sending notifications for ticket {instance.id}")
    
    # Send email notification
    email_success = send_email_notification(instance)
    
    # Send SMS notification if client has phone number
    if instance.client.tel:
        sms_success = send_sms_notification(instance)
    else:
        logger.info(f"No phone number for client {instance.client.username}, skipping SMS")
        
    logger.info(f"Notifications sent for ticket {instance.id} - Email: {'success' if email_success else 'failed'}")
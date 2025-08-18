# products/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Product
from factures.models import Facture
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Product)
def auto_assign_product_to_facture(sender, instance, created, **kwargs):
    """
    Automatically assign products to factures when they become 'done'
    This should run BEFORE the notification signals
    """
    try:
        # Only process when product status changes to 'done' and no facture assigned
        if instance.status == 'done' and not instance.facture:
            logger.info(
                f"Product {instance.id} is done but has no facture, creating/assigning one")

            # Try to find an existing unpaid facture for this client
            existing_facture = Facture.objects.filter(
                client=instance.client,
                payment_status='unpaid'
            ).first()

            if existing_facture:
                # Assign to existing unpaid facture
                instance.facture = existing_facture
                logger.info(
                    f"Assigned product {instance.id} to existing facture {existing_facture.facture_number}")
            else:
                # Create new facture for this client
                new_facture = Facture.objects.create(
                    client=instance.client,
                    # facture_number will be auto-generated in the model
                )
                instance.facture = new_facture
                logger.info(
                    f"Created new facture {new_facture.facture_number} and assigned product {instance.id}")

            # Save the product with the facture assignment
            # Use update_fields to avoid triggering this signal again
            Product.objects.filter(pk=instance.pk).update(
                facture=instance.facture)

            # Refresh instance to get the updated facture
            instance.refresh_from_db()

            logger.info(
                f"Product {instance.id} successfully assigned to facture {instance.facture.facture_number}")

    except Exception as e:
        logger.error(
            f"Error auto-assigning product {instance.id} to facture: {str(e)}")
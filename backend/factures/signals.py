from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from products.models import Product
from .models import Facture
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Product)
def update_facture_pdf_on_product_save(sender, instance, created, **kwargs):
    """
    Signal handler to update facture PDF when a product is saved
    Enhanced to handle status changes specifically
    """
    try:
        # Check if the product is linked to a facture
        if hasattr(instance, 'facture') and instance.facture:
            facture = instance.facture

            # Check if this is a status change to 'done' or if it's already 'done'
            should_update_pdf = False

            if created and instance.status == 'done':
                # New product created with 'done' status
                should_update_pdf = True
                logger.info(
                    f"New product {instance.id} created with 'done' status for facture {facture.facture_number}")
            elif not created:
                # Existing product updated - check if status changed to 'done'
                try:
                    # Get the previous state from database
                    old_instance = Product.objects.get(pk=instance.pk)
                    if old_instance.status != 'done' and instance.status == 'done':
                        should_update_pdf = True
                        logger.info(
                            f"Product {instance.id} status changed to 'done' for facture {facture.facture_number}")
                    elif instance.status == 'done':
                        # Product was already 'done' and still 'done' - might be other field updates
                        should_update_pdf = True
                        logger.info(
                            f"Product {instance.id} (status: done) updated for facture {facture.facture_number}")
                except Product.DoesNotExist:
                    # Fallback if we can't get the old instance
                    if instance.status == 'done':
                        should_update_pdf = True
                        logger.info(
                            f"Product {instance.id} with 'done' status updated for facture {facture.facture_number}")

            if should_update_pdf:
                # Force recalculate totals before PDF generation
                facture.calculate_totals()

                # Refresh the PDF
                pdf_url = facture.refresh_pdf()
                if pdf_url:
                    logger.info(
                        f"PDF updated successfully for facture {facture.facture_number}")
                else:
                    logger.error(
                        f"Failed to update PDF for facture {facture.facture_number}")
            else:
                logger.info(
                    f"Product {instance.id} saved but no PDF update needed (status: {instance.status})")

    except Exception as e:
        logger.error(f"Error in product save signal: {str(e)}")


@receiver(post_delete, sender=Product)
def update_facture_pdf_on_product_delete(sender, instance, **kwargs):
    """
    Signal handler to update facture PDF when a product is deleted
    """
    try:
        # Check if the product was linked to a facture
        if hasattr(instance, 'facture') and instance.facture:
            facture = instance.facture
            logger.info(
                f"Product {instance.id} deleted from facture {facture.facture_number}")

            # Force recalculate totals after deletion
            facture.calculate_totals()

            # Refresh the PDF
            pdf_url = facture.refresh_pdf()
            if pdf_url:
                logger.info(
                    f"PDF updated successfully after product deletion for facture {facture.facture_number}")
            else:
                logger.error(
                    f"Failed to update PDF after product deletion for facture {facture.facture_number}")

    except Exception as e:
        logger.error(f"Error in product delete signal: {str(e)}")



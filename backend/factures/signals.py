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
    """
    try:
        # Check if the product is linked to a facture
        if hasattr(instance, 'facture') and instance.facture:
            facture = instance.facture
            logger.info(
                f"Product {instance.id} saved, updating facture {facture.facture_number} PDF")

            # Refresh the PDF
            pdf_url = facture.refresh_pdf()
            if pdf_url:
                logger.info(
                    f"PDF updated successfully for facture {facture.facture_number}")
            else:
                logger.error(
                    f"Failed to update PDF for facture {facture.facture_number}")

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
                f"Product {instance.id} deleted, updating facture {facture.facture_number} PDF")

            # Refresh the PDF
            pdf_url = facture.refresh_pdf()
            if pdf_url:
                logger.info(
                    f"PDF updated successfully for facture {facture.facture_number}")
            else:
                logger.error(
                    f"Failed to update PDF for facture {facture.facture_number}")

    except Exception as e:
        logger.error(f"Error in product delete signal: {str(e)}")
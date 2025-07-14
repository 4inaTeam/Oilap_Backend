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

                # Refresh the PDF with force regeneration
                pdf_url = facture.refresh_pdf(force_regenerate=True)
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

            # Refresh the PDF with force regeneration
            pdf_url = facture.refresh_pdf(force_regenerate=True)
            if pdf_url:
                logger.info(
                    f"PDF updated successfully after product deletion for facture {facture.facture_number}")
            else:
                logger.error(
                    f"Failed to update PDF after product deletion for facture {facture.facture_number}")

    except Exception as e:
        logger.error(f"Error in product delete signal: {str(e)}")


# Alternative approach: Use a more specific signal for status changes
@receiver(post_save, sender=Product)
def handle_product_status_change_for_pdf(sender, instance, created, **kwargs):
    """
    Enhanced signal specifically for handling status changes that affect PDF generation
    """
    if not hasattr(instance, 'facture') or not instance.facture:
        return

    facture = instance.facture

    try:
        # Always update PDF if the product is 'done' to ensure consistency
        if instance.status == 'done':
            logger.info(
                f"Updating PDF for facture {facture.facture_number} due to product {instance.id} status: {instance.status}")

            # Small delay to ensure database consistency
            import time
            time.sleep(0.1)

            # Force refresh facture from database
            facture.refresh_from_db()

            # Recalculate totals
            facture.calculate_totals()

            # Count done products for debugging
            done_products_count = facture.products.filter(
                status='done').count()
            logger.info(
                f"Facture {facture.facture_number} now has {done_products_count} done products")

            # Force regenerate PDF
            pdf_url = facture.refresh_pdf(force_regenerate=True)

            if pdf_url:
                logger.info(
                    f"SUCCESS: PDF regenerated for facture {facture.facture_number}")
            else:
                logger.error(
                    f"FAILED: PDF regeneration failed for facture {facture.facture_number}")

    except Exception as e:
        logger.error(
            f"Error handling product status change for PDF: {str(e)}", exc_info=True)

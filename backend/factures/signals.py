from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.db import transaction
from django.utils import timezone
from products.models import Product
from users.models import CustomUser, Client
from .models import Facture
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Product)
def handle_facture_creation(sender, instance, created, **kwargs):
    """
    Signal to automatically create CLIENT facture when Product status becomes 'done'
    """
    if instance.status == 'done':
        logger.info(f"Product {instance.id} status is 'done', creating CLIENT facture...")
        
        try:
            with transaction.atomic():
                existing_factures = Facture.objects.filter(product=instance)
                if existing_factures.exists():
                    logger.info(f"Deleting {existing_factures.count()} existing factures for product {instance.id}")
                    existing_factures.delete()

                accountant = CustomUser.objects.filter(role='ACCOUNTANT').first()
                if not accountant:
                    logger.warning("No accountant found in the system")
                
                facture = Facture.objects.create(
                    type='CLIENT',
                    product=instance,
                    client=instance.client,
                    employee=instance.created_by,
                    accountant=accountant
                )
                
                logger.info(f"CLIENT-type facture {facture.id} created successfully for product {instance.id}")
                
        except Exception as e:
            logger.error(f"Error creating facture for product {instance.id}: {str(e)}")
            raise


@receiver(post_save, sender=Facture)
def handle_facture_post_save(sender, instance, created, **kwargs):
    """
    Signal to handle post-save operations for Facture
    """
    if created:
        logger.info(f"New facture created: {instance.id} (Type: {instance.type})")
        
        if instance.type == 'CLIENT':
            try: 
                logger.info(f"QR code processing initiated for facture {instance.id}")
            except Exception as e:
                logger.error(f"Error in QR code processing for facture {instance.id}: {str(e)}")

    if not created:
        if instance.status == 'paid' and not instance.payment_date:
            instance.payment_date = timezone.now()
            Facture.objects.filter(id=instance.id).update(payment_date=instance.payment_date)
            logger.info(f"Payment date set for facture {instance.id}")


@receiver(pre_save, sender=Facture)
def handle_facture_pre_save(sender, instance, **kwargs):
    """
    Signal to handle pre-save operations for Facture
    """
    if not instance.accountant and instance.type == 'CLIENT':
        accountant = CustomUser.objects.filter(role='ACCOUNTANT').first()
        if accountant:
            instance.accountant = accountant
            logger.info(f"Auto-assigned accountant {accountant.id} to facture")
    
    if not instance.due_date:
        instance.due_date = timezone.now().date() + timezone.timedelta(days=15)
        logger.info(f"Auto-set due date for facture: {instance.due_date}")

    if instance.type == 'CLIENT':
        if not instance.client:
            logger.error(f"CLIENT facture must have a client assigned")
            raise ValueError("CLIENT facture must have a client assigned")
        
        if not instance.product:
            logger.error(f"CLIENT facture must have a product assigned")
            raise ValueError("CLIENT facture must have a product assigned")


@receiver(post_save, sender=Facture)
def check_overdue_status(sender, instance, **kwargs):
    """
    Check if facture should be marked as overdue
    This could be called by a periodic task as well
    """
    if (instance.status == 'unpaid' and 
        instance.due_date < timezone.now().date()):
        
        try:
            instance.mark_as_overdue()
            logger.info(f"Facture {instance.id} automatically marked as overdue")
        except Exception as e:
            logger.error(f"Error marking facture {instance.id} as overdue: {str(e)}")


@receiver(post_save, sender=Product)
def handle_product_status_change(sender, instance, **kwargs):
    """
    Handle various product status changes that might affect factures
    """
    if hasattr(instance, '_state') and instance._state.adding:
        return  

    if instance.status != 'done':
        factures = Facture.objects.filter(product=instance, status='unpaid')
        if factures.exists():
            logger.warning(f"Product {instance.id} status changed from 'done', "
                         f"but has {factures.count()} unpaid factures")


@receiver(post_save, sender=Facture)
def log_facture_changes(sender, instance, created, **kwargs):
    """
    Log facture changes for debugging and audit purposes
    """
    if created:
        logger.info(f"AUDIT: Facture {instance.id} created - "
                   f"Type: {instance.type}, Client: {instance.client}, "
                   f"Amount: {instance.total_amount}, Status: {instance.status}")
    else:
        logger.info(f"AUDIT: Facture {instance.id} updated - "
                   f"Status: {instance.status}, Amount: {instance.total_amount}")


@receiver(post_save, sender=Facture)
def generate_qr_code_signal(sender, instance, created, **kwargs):
    """
    Generate QR code after facture creation if not already generated
    """
    if (created and instance.type == 'CLIENT' and 
        instance.total_amount > 0 and not instance.qr_code):
        
        try:
            from django.db import transaction
            transaction.on_commit(lambda: instance.generate_qr_code())
            logger.info(f"QR code generation scheduled for facture {instance.id}")
        except Exception as e:
            logger.error(f"Error scheduling QR code generation for facture {instance.id}: {str(e)}")


@receiver(post_save, sender=Facture)
def generate_pdf_signal(sender, instance, created, **kwargs):
    """
    Generate PDF for CLIENT factures after creation
    """
    if (created and instance.type == 'CLIENT' and 
        instance.total_amount > 0 and not instance.pdf_file):
        
        try:
            from django.db import transaction
            transaction.on_commit(lambda: instance.generate_client_pdf())
            logger.info(f"PDF generation scheduled for facture {instance.id}")
        except Exception as e:
            logger.error(f"Error scheduling PDF generation for facture {instance.id}: {str(e)}")
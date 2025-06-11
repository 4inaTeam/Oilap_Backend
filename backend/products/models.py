from django.db import models, transaction
from users.models import CustomUser
from django.utils import timezone
from datetime import timedelta
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from factures.models import Facture
import logging

logger = logging.getLogger(__name__)


class Product(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('doing', 'Doing'),
        ('done', 'Done'),
        ('canceled', 'Canceled'),
    ]
    PAYEMENT_CHOICES = [
        ('unpaid', 'Unpaid'),
        ('paid', 'Paid'),
    ]
    QUALITY_CHOICES = [
        ('excellente', 'Excellente'),
        ('bonne', 'Bonne'),
        ('moyenne', 'Moyenne'),
        ('mauvaise', 'Mauvaise'),
    ]

    QUALITY_PRICE_MAP = {
        'excellente': 15,
        'bonne': 12,
        'moyenne': 10,
        'mauvaise': 8,
    }

    quality = models.CharField(
        max_length=10, choices=QUALITY_CHOICES, default='moyenne'
    )
    origine = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    quantity = models.PositiveIntegerField(default=1)
    payement = models.CharField(
        max_length=10, choices=PAYEMENT_CHOICES, default='unpaid'
    )
    client = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='products',
        limit_choices_to={'role': 'CLIENT'}
    )
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='created_products'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default='pending'
    )
    estimation_time = models.PositiveIntegerField(
        default=15,
        help_text="Estimated processing time in minutes"
    )
    end_time = models.DateTimeField(null=True, blank=True)

    facture = models.ForeignKey(
        'factures.Facture',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products'
    )

    def save(self, *args, **kwargs):
        """Calculate price based on quality and end_time"""
        logger.info(
            f"Saving product {self.id if self.id else 'new'} - Status: {self.status}, Quality: {self.quality}"
        )

        # Calculate price based on quality
        base_price = self.QUALITY_PRICE_MAP.get(self.quality, 10)
        self.price = base_price * self.quantity

        # Calculate end_time if not set
        if not self.end_time:
            start_time = self.created_at if self.created_at else timezone.now()
            self.end_time = start_time + timedelta(minutes=self.estimation_time)
            logger.info(f"Calculated end_time for product: {self.end_time}")

        logger.info(
            f"Product save - Quality: {self.quality}, Price: {self.price}, Quantity: {self.quantity}"
        )

        super().save(*args, **kwargs)

        logger.info(
            f"Product {self.id} saved successfully with status: {self.status}"
        )

    def __str__(self):
        return f"Product {self.id} - {self.get_status_display()}"

    class Meta:
        ordering = ['end_time']


@receiver(post_save, sender=Product)
def handle_product_status_change(sender, instance, created, **kwargs):
    """Handle facture creation when product status changes to 'done'"""
    if created:
        logger.info(f"New product created: {instance.id}, skipping facture logic")
        return

    try:
        logger.info(
            f"Product status change handler - ID: {instance.pk}, Status: {instance.status}, Payment: {instance.payement}"
        )

        if instance.status == 'done' and instance.payement == 'unpaid':
            with transaction.atomic():
                existing_facture = Facture.objects.filter(
                    client=instance.client,
                    payment_status='unpaid'
                ).first()

                if existing_facture:
                    facture = existing_facture
                    logger.info(f"Using existing facture: {facture.facture_number}")
                else:
                    facture = Facture.objects.create(
                        client=instance.client,
                        payment_status='unpaid',
                        tva_rate=20,
                        credit_card_fee=12
                    )
                    logger.info(f"Created new facture: {facture.facture_number}")

                if instance.facture != facture:
                    Product.objects.filter(pk=instance.pk).update(facture=facture)
                    logger.info(
                        f"Linked product {instance.pk} to facture {facture.facture_number}"
                    )

                facture.calculate_totals()
                facture.save()
                logger.info(
                    f"Updated facture totals - Total: {facture.total_amount}, "
                    f"TVA: {facture.tva_amount}, Final: {facture.final_total}"
                )
    except Exception as e:
        logger.error(f"Error in product status change handler: {str(e)}", exc_info=True)
        raise


@receiver(pre_save, sender=Product)
def handle_product_payment_status(sender, instance, **kwargs):
    """Remove product from facture when payment status changes to 'paid'"""
    if not instance.pk:
        return

    try:
        old_instance = Product.objects.get(pk=instance.pk)

        # Only proceed if payement is changing unpaid -> paid
        if old_instance.payement == 'unpaid' and instance.payement == 'paid':
            logger.info(f"Product {instance.pk} payment status changing from unpaid to paid")

            with transaction.atomic():
                facture = old_instance.facture
                # Unlink the product
                instance.facture = None

                # Recalculate facture totals
                facture.calculate_totals()
                facture.save()

                # If no more unpaid products, mark facture paid
                if not facture.products.filter(payement='unpaid').exists():
                    facture.payment_status = 'paid'
                    facture.save()
                    logger.info(f"Facture {facture.facture_number} marked as paid")

                logger.info(
                    f"Removed product {instance.pk} from facture {facture.facture_number}"
                )
    except Product.DoesNotExist:
        logger.warning(f"Product {instance.pk} not found in pre_save signal")
    except Exception as e:
        logger.error(f"Error in product payment status handler: {str(e)}", exc_info=True)
        raise

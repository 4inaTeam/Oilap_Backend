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

    OLIVE_OIL_YIELD_MAP = {
        'excellente': 0.20,
        'bonne': 0.18,
        'moyenne': 0.17,
        'mauvaise': 0.15,
    }

    WASTE_COEFFICIENTS = {
        'excellente': 0.82,
        'bonne': 0.835,
        'moyenne': 0.85,
        'mauvaise': 0.875,
    }

    quality = models.CharField(
        max_length=10, choices=QUALITY_CHOICES, default='moyenne'
    )
    origine = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    quantity = models.PositiveIntegerField(
        default=1, help_text="Quantity in kg")

    olive_oil_volume = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Calculated olive oil volume in liters"
    )

    total_waste_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Total waste in kg"
    )

    waste_vendus_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=0,
        help_text="Sold waste in kg"
    )

    waste_non_vendus_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Unsold waste in kg"
    )

    waste_vendus_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Revenue from sold waste in DT"
    )

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

    def calculate_olive_oil_volume(self):
        """Calculate the expected olive oil volume based on olive quality and quantity"""
        yield_per_kg = self.OLIVE_OIL_YIELD_MAP.get(self.quality, 0.17)
        return self.quantity * yield_per_kg

    def get_oil_efficiency_percentage(self):
        """Get the oil extraction efficiency as a percentage"""
        yield_per_kg = self.OLIVE_OIL_YIELD_MAP.get(self.quality, 0.17)
        return yield_per_kg * 100

    def calculate_total_waste(self):
        """Calculate total waste based on olive quality and quantity"""
        waste_coefficient = self.WASTE_COEFFICIENTS.get(self.quality, 0.85)
        return self.quantity * waste_coefficient

    def calculate_waste_non_vendus(self):
        """Calculate unsold waste"""
        if self.total_waste_kg:
            return self.total_waste_kg - self.waste_vendus_kg
        return 0

    def get_waste_percentage(self):
        """Get waste percentage from total olives"""
        if self.quantity > 0 and self.total_waste_kg:
            return (self.total_waste_kg / self.quantity) * 100
        return 0

    def get_waste_vendus_percentage(self):
        """Get percentage of sold waste"""
        if self.total_waste_kg and self.total_waste_kg > 0:
            return (self.waste_vendus_kg / self.total_waste_kg) * 100
        return 0

    def sell_waste(self, quantity_sold, price_per_kg):
        """Mark some waste as sold"""
        if self.waste_vendus_kg + quantity_sold <= self.total_waste_kg:
            self.waste_vendus_kg += quantity_sold
            self.waste_vendus_price += quantity_sold * price_per_kg
            self.waste_non_vendus_kg = self.calculate_waste_non_vendus()
            self.save()
            return True
        return False

    def save(self, *args, **kwargs):
        """Calculate price, olive oil volume, and end_time"""
        logger.info(
            f"Saving product {self.id if self.id else 'new'} - Status: {self.status}, Quality: {self.quality}"
        )

        # Calculate price based on quality
        base_price = self.QUALITY_PRICE_MAP.get(self.quality, 10)
        self.price = base_price * self.quantity

        # Calculate olive oil volume
        self.olive_oil_volume = self.calculate_olive_oil_volume()

        # Calculate waste amounts
        self.total_waste_kg = self.calculate_total_waste()
        self.waste_non_vendus_kg = self.calculate_waste_non_vendus()

        # Calculate end_time if not set
        if not self.end_time:
            start_time = self.created_at if self.created_at else timezone.now()
            self.end_time = start_time + \
                timedelta(minutes=self.estimation_time)
            logger.info(f"Calculated end_time for product: {self.end_time}")

        logger.info(
            f"Product save - Quality: {self.quality}, Price: {self.price}, "
            f"Quantity: {self.quantity}kg, Olive Oil Volume: {self.olive_oil_volume}L"
            f"Total Waste: {self.total_waste_kg}kg, Vendus: {self.waste_vendus_kg}kg, Non Vendus: {self.waste_non_vendus_kg}kg"
        )

        super().save(*args, **kwargs)

        logger.info(
            f"Product {self.id} saved successfully with status: {self.status}"
        )

    def __str__(self):
        return f"Product {self.id} - {self.get_status_display()} ({self.quantity}kg → {self.olive_oil_volume}L)"

    class Meta:
        ordering = ['end_time']


@receiver(post_save, sender=Product)
def handle_product_status_change(sender, instance, created, **kwargs):
    """Handle facture creation and notifications when product status changes to 'done'"""
    if created:
        logger.info(
            f"New product created: {instance.id} - {instance.quantity}kg olives "
            f"({instance.quality}) → {instance.olive_oil_volume}L oil, skipping facture logic"
        )
        return

    try:
        logger.info(
            f"Product status change handler - ID: {instance.pk}, Status: {instance.status}, "
            f"Payment: {instance.payement}, Oil Volume: {instance.olive_oil_volume}L"
        )

        if instance.status == 'done' and instance.payement == 'unpaid':
            with transaction.atomic():
                existing_facture = Facture.objects.filter(
                    client=instance.client,
                    payment_status='unpaid'
                ).first()

                if existing_facture:
                    facture = existing_facture
                    logger.info(
                        f"Using existing facture: {facture.facture_number}")
                else:
                    facture = Facture.objects.create(
                        client=instance.client,
                        payment_status='unpaid',
                        tva_rate=20,
                        credit_card_fee=12
                    )
                    logger.info(
                        f"Created new facture: {facture.facture_number}")

                if instance.facture != facture:
                    Product.objects.filter(
                        pk=instance.pk).update(facture=facture)
                    logger.info(
                        f"Linked product {instance.pk} to facture {facture.facture_number}"
                    )

                facture.calculate_totals()
                facture.save()
                logger.info(
                    f"Updated facture totals - Total: {facture.total_amount}, "
                    f"TVA: {facture.tva_amount}, Final: {facture.final_total}"
                )

                # Enhanced notification sending with oil volume info
                logger.info(
                    f"Starting notification process for product {instance.id} "
                    f"({instance.quantity}kg → {instance.olive_oil_volume}L oil)"
                )

                # Debug user notification settings
                user_debug_info = instance.client.get_notification_debug_info()
                logger.info(
                    f"User {instance.client.id} notification debug: {user_debug_info}")

                # Import notification functions
                from tickets.utils import (
                    send_push_notification_for_product,
                    send_email_notification_for_product,
                    send_sms_notification_for_product
                )

                # Try to import and create notification record
                try:
                    from tickets.models import Notification
                    notification = Notification.create_product_ready_notification(
                        user=instance.client,
                        product=instance,
                        facture=facture
                    )
                    logger.info(
                        f"Created notification record: {notification.id}")
                except ImportError:
                    logger.warning(
                        "Notification model not available, skipping database record")
                except Exception as e:
                    logger.error(
                        f"Error creating notification record: {str(e)}")

                # Initialize notification results
                notification_results = {
                    'push': False,
                    'email': False,
                    'sms': False
                }

                # Send push notification with enhanced error handling
                try:
                    if instance.client.can_receive_push_notifications():
                        logger.info(
                            f"User {instance.client.id} can receive push notifications, sending...")
                        push_success = send_push_notification_for_product(
                            user=instance.client,
                            product=instance,
                            facture=facture
                        )
                        notification_results['push'] = push_success
                        if push_success:
                            logger.info(
                                f"Push notification sent successfully for product {instance.id}")
                        else:
                            logger.warning(
                                f"Push notification failed for product {instance.id}")
                    else:
                        logger.info(
                            f"User {instance.client.id} cannot receive push notifications, skipping...")
                except Exception as e:
                    logger.error(
                        f"Error sending push notification for product {instance.id}: {str(e)}")

                # Send email notification
                try:
                    if instance.client.can_receive_email_notifications():
                        logger.info(
                            f"User {instance.client.id} can receive email notifications, sending...")
                        email_success = send_email_notification_for_product(
                            user=instance.client,
                            product=instance,
                            facture=facture
                        )
                        notification_results['email'] = email_success
                        if email_success:
                            logger.info(
                                f"Email notification sent successfully for product {instance.id}")
                        else:
                            logger.warning(
                                f"Email notification failed for product {instance.id}")
                    else:
                        logger.info(
                            f"User {instance.client.id} cannot receive email notifications, skipping...")
                except Exception as e:
                    logger.error(
                        f"Error sending email notification for product {instance.id}: {str(e)}")

                # Send SMS notification
                try:
                    if instance.client.can_receive_sms_notifications():
                        logger.info(
                            f"User {instance.client.id} can receive SMS notifications, sending...")
                        sms_success = send_sms_notification_for_product(
                            user=instance.client,
                            product=instance,
                            facture=facture
                        )
                        notification_results['sms'] = sms_success
                        if sms_success:
                            logger.info(
                                f"SMS notification sent successfully for product {instance.id}")
                        else:
                            logger.warning(
                                f"SMS notification failed for product {instance.id}")
                    else:
                        logger.info(
                            f"User {instance.client.id} cannot receive SMS notifications, skipping...")
                except Exception as e:
                    logger.error(
                        f"Error sending SMS notification for product {instance.id}: {str(e)}")

                # Log final results
                successful_notifications = [
                    k for k, v in notification_results.items() if v]
                failed_notifications = [
                    k for k, v in notification_results.items() if not v]

                logger.info(
                    f"Notification process completed for product {instance.id}. "
                    f"Successful: {successful_notifications}, Failed: {failed_notifications}"
                )

                # If no notifications were sent, this might indicate a problem
                if not any(notification_results.values()):
                    logger.warning(
                        f"No notifications were sent for product {instance.id}. "
                        f"User {instance.client.id} notification settings: {user_debug_info}"
                    )

    except Exception as e:
        logger.error(
            f"Error in product status change handler: {str(e)}", exc_info=True)
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
            logger.info(
                f"Product {instance.pk} payment status changing from unpaid to paid "
                f"({instance.quantity}kg → {instance.olive_oil_volume}L oil)"
            )

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
                    logger.info(
                        f"Facture {facture.facture_number} marked as paid")

                logger.info(
                    f"Removed product {instance.pk} from facture {facture.facture_number}"
                )
    except Product.DoesNotExist:
        logger.warning(f"Product {instance.pk} not found in pre_save signal")
    except Exception as e:
        logger.error(
            f"Error in product payment status handler: {str(e)}", exc_info=True)
        raise

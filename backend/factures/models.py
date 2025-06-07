from django.db import models
from django.contrib.auth import get_user_model
from decimal import Decimal
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

User = get_user_model()


class Facture(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ('unpaid', 'Unpaid'),
        ('paid', 'Paid'),
        ('partial', 'Partial'),
    ]

    client = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='factures',
        limit_choices_to={'role': 'CLIENT'}
    )
    facture_number = models.CharField(max_length=20, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    payment_status = models.CharField(
        max_length=10,
        choices=PAYMENT_STATUS_CHOICES,
        default='unpaid'
    )
    total_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0)
    tva_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=20)  # Default 20%
    tva_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0)
    credit_card_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=12)
    final_total = models.DecimalField(
        max_digits=10, decimal_places=2, default=0)

    stripe_payment_intent = models.CharField(
        max_length=255, blank=True, null=True)

    pdf_url = models.URLField(blank=True, null=True,
                              help_text="Cloudinary URL for the PDF")
    pdf_public_id = models.CharField(
        max_length=255, blank=True, null=True, help_text="Cloudinary public ID for the PDF")

    def save(self, *args, **kwargs):
        try:
            is_new = not self.pk
            if not self.facture_number:
                self.facture_number = self.generate_facture_number()

            # Calculate totals BEFORE saving
            self.calculate_totals()

            super().save(*args, **kwargs)

            # Generate PDF after saving (so we have an ID)
            if is_new or not self.pdf_url:
                from .utils import generate_and_upload_facture_pdf
                pdf_url = generate_and_upload_facture_pdf(self)
                if pdf_url and not self.pdf_url:
                    # Update without triggering save again
                    Facture.objects.filter(pk=self.pk).update(
                        pdf_url=pdf_url,
                        pdf_public_id=self.pdf_public_id
                    )

            if is_new:
                logger.info(
                    f"Created new facture {self.facture_number} for client {self.client.username}")

        except Exception as e:
            logger.error(f"Error saving facture: {str(e)}")
            raise

    def generate_facture_number(self):
        """Generate unique facture number"""
        from datetime import datetime
        date_str = datetime.now().strftime('%Y%m%d')
        last_facture = Facture.objects.filter(
            facture_number__startswith=f'FAC-{date_str}'
        ).order_by('-facture_number').first()

        if last_facture:
            last_num = int(last_facture.facture_number.split('-')[-1])
            new_num = last_num + 1
        else:
            new_num = 1

        return f'FAC-{date_str}-{new_num:04d}'

    def calculate_totals(self):
        """Calculate all totals for the facture"""
        try:
            # Get all products for this facture that are done and unpaid
            products_total = Decimal('0.00')
            
            # Check if we have products relation
            if hasattr(self, 'products'):
                products_total = sum(
                    Decimal(str(product.price)) * Decimal(str(product.quantity))
                    for product in self.products.all()
                    if product.status == 'done'
                )
            
            self.total_amount = products_total
            self.tva_amount = self.total_amount * (self.tva_rate / Decimal('100'))
            self.final_total = self.total_amount + self.tva_amount + self.credit_card_fee

            logger.info(f"Calculated totals for facture {self.facture_number if self.facture_number else 'new'}: "
                        f"Products Total={self.total_amount}, TVA={self.tva_amount}, Final={self.final_total}")

        except Exception as e:
            logger.error(f"Error calculating totals: {str(e)}")
            # Set safe defaults
            self.total_amount = Decimal('0.00')
            self.tva_amount = Decimal('0.00')
            self.final_total = self.credit_card_fee

    def __str__(self):
        return f"Facture {self.facture_number} - {self.client.username}"

    class Meta:
        ordering = ['-created_at']
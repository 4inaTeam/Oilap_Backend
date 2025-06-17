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
        max_digits=5, decimal_places=2, default=20)
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
            
            # Generate facture number if new
            if not self.facture_number:
                self.facture_number = self.generate_facture_number()

            # First save to get the primary key
            super().save(*args, **kwargs)

            # Calculate totals after saving (so we have access to related products)
            self.calculate_totals()
            
            # Update the calculated fields without triggering save again
            Facture.objects.filter(pk=self.pk).update(
                total_amount=self.total_amount,
                tva_amount=self.tva_amount,
                final_total=self.final_total
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
            products_total = Decimal('0.00')
        
            if hasattr(self, 'products'):
                products_total = sum(
                    Decimal(str(product.price))
                    for product in self.products.all()
                    if product.status == 'done'
                )
        
            self.total_amount = products_total
            self.tva_amount = self.total_amount * (self.tva_rate / Decimal('100'))
            # Remove credit card fee from final total calculation
            self.final_total = self.total_amount + self.tva_amount
        
            logger.info(f"Calculated totals for facture {self.facture_number if self.facture_number else 'new'}: "
                        f"Products Total={self.total_amount}, TVA={self.tva_amount}, Final={self.final_total}")
        
        except Exception as e:
            logger.error(f"Error calculating totals: {str(e)}")
            # Set safe defaults
            self.total_amount = Decimal('0.00')
            self.tva_amount = Decimal('0.00')
            self.final_total = Decimal('0.00')

    def refresh_pdf(self):
        """Method to refresh PDF when products are updated"""
        try:
            from .utils import generate_and_upload_facture_pdf
            
            # Recalculate totals first
            self.calculate_totals()
            
            # Update the database with new totals
            Facture.objects.filter(pk=self.pk).update(
                total_amount=self.total_amount,
                tva_amount=self.tva_amount,
                final_total=self.final_total
            )
            
            # Regenerate PDF
            pdf_url = generate_and_upload_facture_pdf(self, force_regenerate=True)
            if pdf_url:
                logger.info(f"PDF refreshed for facture {self.facture_number}")
                return pdf_url
            else:
                logger.error(f"Failed to refresh PDF for facture {self.facture_number}")
                return None
                
        except Exception as e:
            logger.error(f"Error refreshing PDF: {str(e)}")
            return None

    def __str__(self):
        return f"Facture {self.facture_number} - {self.client.username}"

    class Meta:
        ordering = ['-created_at']
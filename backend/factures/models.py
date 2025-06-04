import uuid
import qrcode
import json
from django.db import models
from django.utils import timezone
from users.models import CustomUser, Client
from products.models import Product
from decimal import Decimal
from io import BytesIO
from django.core.files import File
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.exceptions import ValidationError
import os
import logging

logger = logging.getLogger(__name__)


class Facture(models.Model):
    TYPE_CHOICES = [
        ('CLIENT', 'Client Facture'),
        ('ELECTRICITY', 'Electricity Facture'),
        ('WATER', 'Water Facture'),
        ('PURCHASE', 'Purchase Facture'),
    ]
    type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default='CLIENT'
    )
    STATUS_CHOICES = [
        ('unpaid', 'Unpaid'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('pending_review', 'Pending Review'),
    ]
    predicted_type = models.CharField(
        max_length=12,
        choices=TYPE_CHOICES,
        null=True,
        blank=True
    )
    needs_review = models.BooleanField(default=False)
    original_filename = models.CharField(max_length=255, null=True, blank=True)
    file_metadata = models.JSONField(default=dict, blank=True)
    processing_metadata = models.JSONField(default=dict, blank=True)

    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name='facture',
        null=True,
        blank=True
    )
    client = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='factures',
        limit_choices_to={'role': 'CLIENT'},
        null=True,
        blank=True
    )

    employee = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generated_factures'
    )
    accountant = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_factures'
    )
    base_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        editable=False
    )
    tax_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        editable=False
    )
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        editable=False
    )
    issue_date = models.DateField(auto_now_add=True)
    due_date = models.DateField(
        default=timezone.now().date() + timezone.timedelta(days=15)
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='unpaid'
    )
    payment_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    qr_code = models.ImageField(upload_to='qr_codes/', blank=True)
    payment_uuid = models.UUIDField(
        default=uuid.uuid4, editable=False, null=True)
    qr_verified = models.BooleanField(default=False)

    image = models.ImageField(
        upload_to='facture_images/',
        max_length=255,
        null=True,
        blank=True
    )
    pdf_file = models.FileField(
        upload_to='facture_pdfs/',
        null=True,
        blank=True,
        editable=False
    )

    class Meta:
        ordering = ['-due_date']
        indexes = [
            models.Index(fields=['status', 'due_date']),
            models.Index(fields=['type', 'status']),
            models.Index(fields=['client', 'status']),
        ]

    def __str__(self):
        return f"FACT-{self.id}-{self.get_type_display()}"

    def clean(self):
        """Custom validation for Facture model"""
        super().clean()

        # CLIENT type specific validations
        if self.type == 'CLIENT':
            if not self.client:
                raise ValidationError(
                    {'client': 'Client is required for CLIENT type factures.'})
            if not self.product:
                raise ValidationError(
                    {'product': 'Product is required for CLIENT type factures.'})

        # Ensure amounts are positive
        if self.base_amount < 0:
            raise ValidationError(
                {'base_amount': 'Base amount cannot be negative.'})

    def save(self, *args, **kwargs):
        """Override save to handle automatic calculations and QR code generation"""
        self.full_clean()

        # Calculate amounts for CLIENT type factures
        if self.type == 'CLIENT' and self.product:
            if hasattr(self.product, 'price') and hasattr(self.product, 'quantity'):
                # Calculate based on product price and quantity
                self.base_amount = Decimal(
                    str(self.product.price)) * Decimal(str(self.product.quantity))
            elif hasattr(self.product, 'total_price'):
                # Use total price from product
                self.base_amount = Decimal(str(self.product.total_price))
            else:
                # Fallback to a default calculation or existing value
                if not self.base_amount:
                    self.base_amount = Decimal('0.00')

            # Calculate tax (20% for Tunisia)
            self.tax_amount = self.base_amount * Decimal('0.20')
            self.total_amount = self.base_amount + self.tax_amount

        # For non-CLIENT factures, ensure calculations are done if base_amount exists
        elif self.base_amount and self.type != 'CLIENT':
            if not self.tax_amount:
                self.tax_amount = self.base_amount * Decimal('0.20')
            if not self.total_amount:
                self.total_amount = self.base_amount + self.tax_amount

        # Set due date if not provided
        if not self.due_date:
            self.due_date = timezone.now().date() + timezone.timedelta(days=15)

        super().save(*args, **kwargs)

        # Generate QR code after saving (when we have an ID)
        if self.type == 'CLIENT' and not self.qr_code:
            try:
                self.generate_qr_code()
                # Save again to update QR code field without triggering recursion
                super(Facture, self).save(update_fields=['qr_code'])
            except Exception as e:
                logger.error(
                    f"Failed to generate QR code for facture {self.id}: {str(e)}")

    def generate_qr_code(self):
        """Generate QR code for payment"""
        if not self.id:
            logger.warning("Cannot generate QR code for unsaved facture")
            return

        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )

            data = {
                "facture_id": self.id,
                "uuid": str(self.payment_uuid),
                "amount": str(self.total_amount),
                "currency": "TND",  # Tunisian Dinar
                "type": self.type,
                "issue_date": self.issue_date.isoformat(),
            }

            qr.add_data(json.dumps(data))
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)

            self.qr_code.save(
                f'facture_{self.id}_qr.png',
                File(buffer),
                save=False
            )
            logger.info(
                f"QR code generated successfully for facture {self.id}")

        except Exception as e:
            logger.error(
                f"Error generating QR code for facture {self.id}: {str(e)}")
            raise

    def generate_client_pdf(self):
        """Generate professional PDF for CLIENT factures using ReportLab"""
        if self.type != 'CLIENT':
            logger.warning(
                f"PDF generation only available for CLIENT factures, got {self.type}")
            return

        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
            from reportlab.lib.units import mm
            from reportlab.lib.colors import black, grey, darkblue
            from django.core.files.base import ContentFile

            buffer = BytesIO()
            p = canvas.Canvas(buffer, pagesize=A4)
            width, height = A4

            # Company header
            p.setFont("Helvetica-Bold", 16)
            p.drawRightString(width - 40, height - 40, "Facture")

            p.setFont("Helvetica-Bold", 12)
            p.drawRightString(width - 40, height - 60, "Nom de l'usine")

            p.setFont("Helvetica", 9)
            p.drawRightString(width - 40, height - 75, "REG: 12300012300")
            p.drawRightString(width - 40, height - 90,
                              "ma3melFoulen@gmail.com | +216 33 524 415")

            # Client section
            if self.client:
                p.setFont("Helvetica-Bold", 12)
                client_name = self.client.get_full_name() if hasattr(
                    self.client, 'get_full_name') else str(self.client)
                p.drawRightString(width - 40, height - 120, client_name)

            # Invoice details
            p.setFont("Helvetica", 9)
            p.drawString(40, height - 140,
                         f"NUMÉRO DE FACTURE : FAC-{self.id:04d}")
            p.drawString(
                40, height - 155, f"DATE DE FACTURE : {self.issue_date.strftime('%d %b %Y')}")
            p.drawString(
                40, height - 170, f"DATE D'ÉCHÉANCE : {self.due_date.strftime('%d %b %Y')}")

            # Products table header
            y_pos = height - 220
            p.setFillColorRGB(0.8, 0.8, 1.0)  # Light blue background
            p.rect(40, y_pos - 15, width - 80, 25, fill=1, stroke=1)
            p.setFillColorRGB(0, 0, 0)  # Black text

            p.setFont("Helvetica-Bold", 10)
            col_widths = [120, 80, 80, 80, 80]
            headers = ["Produit", "Quantité",
                       "Production", "Prix Unitaire", "Total"]
            x_pos = 50

            for i, header in enumerate(headers):
                p.drawString(x_pos, y_pos - 5, header)
                x_pos += col_widths[i]

            # Product details
            y_pos -= 30
            p.setFont("Helvetica", 9)
            if self.product:
                product_name = getattr(
                    self.product, 'name', f'Product {self.product.id}')
                quantity = getattr(self.product, 'quantity', 1)
                price = getattr(self.product, 'price', self.base_amount)

                x_pos = 50
                p.drawString(x_pos, y_pos, product_name)
                x_pos += col_widths[0]
                p.drawString(x_pos, y_pos, f"{quantity} Kg")
                x_pos += col_widths[1]
                p.drawString(x_pos, y_pos, f"{quantity} L")
                x_pos += col_widths[2]
                p.drawString(x_pos, y_pos, f"{price} DT")
                x_pos += col_widths[3]
                p.drawString(x_pos, y_pos, f"{self.base_amount} DT")

            # Totals section
            y_pos = height - 400
            p.setFont("Helvetica", 10)

            totals_x = width - 200
            p.drawString(totals_x, y_pos, f"Sous-total: {self.base_amount} DT")
            y_pos -= 20
            p.drawString(totals_x, y_pos, f"TVA (20%): {self.tax_amount} DT")
            y_pos -= 20
            p.setFont("Helvetica-Bold", 12)
            p.drawString(totals_x, y_pos, f"Total: {self.total_amount} DT")

            # Payment instructions
            y_pos -= 60
            p.setFont("Helvetica", 9)
            payment_text = [
                "INSTRUCTIONS DE PAIEMENT",
                "",
                "Nom de l'usine",
                "SWIFT/IBAN: NZ0201230012",
                "Numéro de compte: 12-1234-1234256-12",
                "",
                "Pour toute question, veuillez nous contacter :",
                "ma3melFoulen@gmail.com | +216 33 524 415"
            ]

            for line in payment_text:
                if line == "INSTRUCTIONS DE PAIEMENT":
                    p.setFont("Helvetica-Bold", 10)
                else:
                    p.setFont("Helvetica", 9)
                p.drawString(40, y_pos, line)
                y_pos -= 15

            # Add QR code if available
            if self.qr_code and os.path.exists(self.qr_code.path):
                try:
                    p.drawImage(self.qr_code.path, width -
                                150, 50, width=80, height=80)
                except Exception as e:
                    logger.warning(f"Could not add QR code to PDF: {str(e)}")

            p.showPage()
            p.save()
            buffer.seek(0)

            # Save PDF to model
            pdf_content = ContentFile(buffer.getvalue())
            self.pdf_file.save(
                f'facture_{self.id}_client.pdf',
                pdf_content,
                save=False
            )

            logger.info(f"PDF generated successfully for facture {self.id}")

        except Exception as e:
            logger.error(
                f"Error generating PDF for facture {self.id}: {str(e)}")
            raise

    def mark_as_paid(self):
        """Mark facture as paid and set payment date"""
        self.status = 'paid'
        self.payment_date = timezone.now()
        self.save(update_fields=['status', 'payment_date'])
        logger.info(f"Facture {self.id} marked as paid")

    def mark_as_overdue(self):
        """Mark facture as overdue if past due date and unpaid"""
        if self.status == 'unpaid' and self.due_date < timezone.now().date():
            self.status = 'overdue'
            self.save(update_fields=['status'])
            logger.info(f"Facture {self.id} marked as overdue")

    @property
    def is_overdue(self):
        """Check if facture is overdue"""
        return (self.status in ['unpaid', 'overdue'] and
                self.due_date < timezone.now().date())

    @property
    def days_until_due(self):
        """Calculate days until due date"""
        delta = self.due_date - timezone.now().date()
        return delta.days

    def __repr__(self):
        return f"<Facture(id={self.id}, type={self.type}, status={self.status}, amount={self.total_amount})>"

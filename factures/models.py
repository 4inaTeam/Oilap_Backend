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
        default=Decimal('0.00'),  # Add default
        editable=False
    )
    tax_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),  # Add default
        editable=False
    )
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),  # Add default
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
    payment_uuid = models.UUIDField(default=uuid.uuid4, editable=False, null=True)
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
        ]

    def __str__(self):
        return f"FACT-{self.id}-{self.get_type_display()}"

    def generate_qr_code(self):
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
            "currency": "EUR"
        }
        
        qr.add_data(json.dumps(data))
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer)
        
        self.qr_code.save(f'facture_{self.id}_qr.png', File(buffer), save=False)

    def clean(self):
        """Add model-level validation"""
        super().clean()

        if self.predicted_type and self.predicted_type not in dict(self.TYPE_CHOICES):
            raise ValidationError({'predicted_type': 'Invalid predicted type'})
        
        # Client invoices must have a product with a client
        if self.type == 'CLIENT':
            if not self.product:
                raise ValidationError("Client invoices require a product")
            if not self.product.client:
                raise ValidationError("Selected product has no associated client")
        else:
            # Non-client invoices shouldn't have products
            if self.product:
                raise ValidationError("Non-client invoices cannot have products")

    def save(self, *args, **kwargs):
        """Updated save method with validation"""
        if not self.pk:  # Only on initial creation
            if self.type == 'CLIENT':
                # These checks are now in clean()
                self.client = self.product.client
                self.base_amount = self.product.price * self.product.quantity
                self.tax_amount = self.base_amount * Decimal('0.20')
                self.total_amount = self.base_amount + self.tax_amount
                self.due_date = timezone.now() + timezone.timedelta(days=30)
            else:
                # Clear product/client for non-client invoices
                self.product = None
                self.client = None
                self.base_amount = Decimal('0.00')
                self.tax_amount = Decimal('0.00')
                self.total_amount = Decimal('0.00')
                if not self.due_date:
                    self.due_date = timezone.now() + timezone.timedelta(days=15)
        
        # Run full validation before saving
        self.full_clean()
        super().save(*args, **kwargs)
    def create(self, validated_data):
        # if non-client and no due_date provided, set a default
        if validated_data.get('type') != 'CLIENT' and 'due_date' not in validated_data:
            validated_data['due_date'] = (
                timezone.now() + timezone.timedelta(days=15)
            ).date()
        return super().create(validated_data)

@receiver(post_save, sender=Facture)
def generate_qr_code(sender, instance, created, **kwargs):
    if created and not instance.qr_code:
        instance.generate_qr_code()
        instance.save()

@receiver(post_save, sender=Facture)
def generate_non_client_pdf(sender, instance, created, **kwargs):
    if created and instance.type != 'CLIENT' and instance.image:
        import img2pdf
        from django.core.files.base import ContentFile

        try:
            image_file = instance.image.open()
            pdf_bytes = img2pdf.convert(image_file.read())
            image_file.close()

            pdf_name = f"facture_{instance.id}.pdf"
            instance.pdf_file.save(pdf_name, ContentFile(pdf_bytes), save=True)

            instance.save()
        except Exception as e:
            print(f"Error generating PDF: {e}")
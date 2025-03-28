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

class Facture(models.Model):
    STATUS_CHOICES = [
        ('unpaid', 'Unpaid'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
    ]
    
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name='facture'
    )
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='factures'
    )
    employee = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name='generated_factures'
    )
    accountant = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name='managed_factures'
    )
    base_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        editable=False
    )
    tax_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        editable=False
    )
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        editable=False
    )
    issue_date = models.DateField(auto_now_add=True)
    due_date = models.DateField()
    status = models.CharField(
        max_length=7,
        choices=STATUS_CHOICES,
        default='unpaid'
    )
    payment_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    qr_code = models.ImageField(upload_to='qr_codes/', blank=True)
    payment_uuid = models.UUIDField(default=uuid.uuid4, editable=False, null=True)
    qr_verified = models.BooleanField(default=False)

    class Meta:
        ordering = ['-due_date']
        indexes = [
            models.Index(fields=['status', 'due_date']),
        ]

    def __str__(self):
        return f"FACT-{self.id}-{self.product.name[:10]}"

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

    def save(self, *args, **kwargs):
        if not self.pk:
            self.base_amount = self.product.price * self.product.quantity
            self.tax_amount = self.base_amount * Decimal('0.20')
            self.total_amount = self.base_amount + self.tax_amount
            self.due_date = timezone.now() + timezone.timedelta(days=30)
        super().save(*args, **kwargs)

@receiver(post_save, sender=Facture)
def generate_qr_code(sender, instance, created, **kwargs):
    if created and not instance.qr_code:
        instance.generate_qr_code()
        instance.save()
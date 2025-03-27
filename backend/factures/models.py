from django.db import models
from django.utils import timezone
from users.models import CustomUser, Client
from products.models import Product
from decimal import Decimal


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

    class Meta:
        ordering = ['-due_date']
        indexes = [
            models.Index(fields=['status', 'due_date']),
        ]

    def __str__(self):
        return f"FACT-{self.id}-{self.product.name[:10]}"

    def save(self, *args, **kwargs):
        if not self.pk:
            self.base_amount = self.product.price * self.product.quantity
            self.tax_amount = self.base_amount * Decimal('0.20')
            self.total_amount = self.base_amount + self.tax_amount
            self.due_date = timezone.now() + timezone.timedelta(days=30)
        super().save(*args, **kwargs)
from django.db import models
from factures.models import Facture

class Payment(models.Model):
    facture = models.OneToOneField(
        Facture,
        on_delete=models.PROTECT,
        related_name='payment'
    )
    stripe_payment_intent = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='TUN')
    status = models.CharField(max_length=20, default='requires_payment_method')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Payment-{self.facture.id}-{self.status}"
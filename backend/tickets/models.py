from django.db import models
from products.models import Product
from users.models import CustomUser
from factures.models import Facture


class Ticket(models.Model):
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name='ticket',
    )
    client = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='tickets',
        limit_choices_to={'role': 'CLIENT'}
    )
    facture = models.ForeignKey(
        Facture,
        on_delete=models.CASCADE,
        related_name='tickets'
    )
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Ticket for {self.client.username} - {self.product.id}"

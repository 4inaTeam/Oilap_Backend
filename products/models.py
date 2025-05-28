from django.db import models
from users.models import CustomUser, Client


class Product(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('doing', 'Doing'),
        ('done', 'Done'),
        ('canceled', 'Canceled'),
    ]

    quality = models.TextField(blank=True, null=True)
    origine = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    photo = models.ImageField(
        upload_to='products/',
        blank=True,
        null=True,
        default='products/default.jpg'
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
        max_length=10, choices=STATUS_CHOICES, default='pending')
    estimation_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Product {self.id} - {self.get_status_display()}"

from django.db import models
from users.models import CustomUser, Client
from django.utils import timezone
from datetime import timedelta


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

    estimation_time = models.PositiveIntegerField(
        default=15,
        help_text="Estimated processing time in minutes"
    )

    end_time = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        """Override save to calculate end_time based on created_at and estimation_time"""
        if not self.end_time:
            start_time = self.created_at if self.created_at else timezone.now()
            self.end_time = start_time + \
                timedelta(minutes=self.estimation_time)

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Product {self.id} - {self.get_status_display()}"

    class Meta:
        ordering = ['end_time']

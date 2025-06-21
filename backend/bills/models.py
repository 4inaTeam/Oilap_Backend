from django.db import models
from django.utils import timezone
from users.models import CustomUser


class Bill(models.Model):
    CATEGORY_CHOICES = [
        ('water', 'Water'),
        ('electricity', 'Electricity'),
        ('purchase', 'Purchase'),
    ]

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='bills'
    )
    owner = models.CharField(
        max_length=255,
        null=False,
        blank=False,
    )
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )
    payment_date = models.DateField(
        default=timezone.now
    )
    consumption = models.FloatField(
        null=True,
        blank=True,
        help_text="kWh for electricity, m³ for water"
    )
    items = models.JSONField(
        null=True,
        blank=True,
        help_text="List of purchased items in JSON format"
    )
    original_image = models.ImageField(
        upload_to='bills/original/'
    )
    pdf_file = models.FileField(
        upload_to='bills/pdf/',
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.category} Bill - {self.payment_date}"

# bills/models.py
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
    # REMOVED: items JSONField
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

# NEW ITEM MODEL
class Item(models.Model):
    bill = models.ForeignKey(
        Bill,
        on_delete=models.CASCADE,
        related_name='items'
    )
    title = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.title} ({self.quantity} x {self.unit_price})"
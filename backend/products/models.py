from django.db import models
from users.models import CustomUser
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class Product(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('doing', 'Doing'),
        ('done', 'Done'),
        ('canceled', 'Canceled'),
    ]
    PAYEMENT_CHOICES = [
        ('unpaid', 'Unpaid'),
        ('paid', 'Paid'),
    ]
    QUALITY_CHOICES = [
        ('excellente', 'Excellente'),
        ('bonne', 'Bonne'),
        ('moyenne', 'Moyenne'),
        ('mauvaise', 'Mauvaise'),
    ]

    QUALITY_PRICE_MAP = {
        'excellente': Decimal('15'),
        'bonne': Decimal('12'),
        'moyenne': Decimal('10'),
        'mauvaise': Decimal('8'),
    }

    OLIVE_OIL_YIELD_MAP = {
        'excellente': Decimal('0.20'),
        'bonne': Decimal('0.18'),
        'moyenne': Decimal('0.17'),
        'mauvaise': Decimal('0.15'),
    }

    WASTE_COEFFICIENTS = {
        'excellente': Decimal('0.82'),
        'bonne': Decimal('0.835'),
        'moyenne': Decimal('0.85'),
        'mauvaise': Decimal('0.875'),
    }

    WASTE_SOLD_PERCENTAGE = {
        'excellente': Decimal('0.75'),
        'bonne': Decimal('0.65'),       
        'moyenne': Decimal('0.50'),    
        'mauvaise': Decimal('0.30'),    
    }

    WASTE_PRICE_PER_KG = {
        'excellente': Decimal('5.50'), 
        'bonne': Decimal('4.80'),       
        'moyenne': Decimal('4.00'),    
        'mauvaise': Decimal('3.20'),    
    }

    quality = models.CharField(
        max_length=10, choices=QUALITY_CHOICES, default='moyenne'
    )
    origine = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    quantity = models.PositiveIntegerField(
        default=1, help_text="Quantity in kg")

    olive_oil_volume = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Calculated olive oil volume in liters"
    )

    total_waste_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Total waste in kg"
    )

    waste_vendus_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Automatically calculated sold waste in kg"
    )

    waste_non_vendus_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Automatically calculated unsold waste in kg"
    )

    waste_vendus_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Automatically calculated revenue from sold waste in DT"
    )

    payement = models.CharField(
        max_length=10, choices=PAYEMENT_CHOICES, default='unpaid'
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
        max_length=10, choices=STATUS_CHOICES, default='pending'
    )
    estimation_time = models.PositiveIntegerField(
        default=15,
        help_text="Estimated processing time in minutes"
    )
    end_time = models.DateTimeField(null=True, blank=True)

    facture = models.ForeignKey(
        'factures.Facture',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products'
    )

    def calculate_olive_oil_volume(self):
        """Calculate the expected olive oil volume based on olive quality and quantity"""
        yield_per_kg = self.OLIVE_OIL_YIELD_MAP.get(
            self.quality, Decimal('0.17'))
        return Decimal(str(self.quantity)) * yield_per_kg

    def get_oil_efficiency_percentage(self):
        """Get the oil extraction efficiency as a percentage"""
        yield_per_kg = self.OLIVE_OIL_YIELD_MAP.get(
            self.quality, Decimal('0.17'))
        return float(yield_per_kg * Decimal('100'))

    def calculate_total_waste(self):
        """Calculate total waste based on olive quality and quantity"""
        waste_coefficient = self.WASTE_COEFFICIENTS.get(
            self.quality, Decimal('0.85'))
        return Decimal(str(self.quantity)) * waste_coefficient

    def calculate_waste_vendus_automatically(self):
        """Automatically calculate how much waste is sold based on quality"""
        if not self.total_waste_kg:
            return Decimal('0')
        
        sold_percentage = self.WASTE_SOLD_PERCENTAGE.get(
            self.quality, Decimal('0.50'))
        return self.total_waste_kg * sold_percentage

    def calculate_waste_vendus_price_automatically(self):
        """Automatically calculate waste vendus price"""
        if not self.waste_vendus_kg:
            return Decimal('0')
        
        price_per_kg = self.WASTE_PRICE_PER_KG.get(
            self.quality, Decimal('4.00'))
        return self.waste_vendus_kg * price_per_kg

    def calculate_waste_non_vendus(self):
        """Calculate unsold waste"""
        if self.total_waste_kg and self.waste_vendus_kg:
            return self.total_waste_kg - self.waste_vendus_kg
        return Decimal('0')

    def get_waste_percentage(self):
        """Get waste percentage from total olives"""
        if self.quantity > 0 and self.total_waste_kg:
            percentage = (self.total_waste_kg /
                          Decimal(str(self.quantity))) * Decimal('100')
            return float(percentage)
        return 0.0

    def get_waste_vendus_percentage(self):
        """Get percentage of sold waste"""
        if self.total_waste_kg and self.total_waste_kg > 0 and self.waste_vendus_kg:
            percentage = (self.waste_vendus_kg / self.total_waste_kg) * Decimal('100')
            return float(percentage)
        return 0.0

    def save(self, *args, **kwargs):
        """Calculate all values automatically"""
        logger.info(
            f"Saving product {self.id if self.id else 'new'} - Status: {self.status}, Quality: {self.quality}"
        )

        base_price = self.QUALITY_PRICE_MAP.get(self.quality, Decimal('10'))
        self.price = base_price * Decimal(str(self.quantity))

        self.olive_oil_volume = self.calculate_olive_oil_volume()

        self.total_waste_kg = self.calculate_total_waste()
        self.waste_vendus_kg = self.calculate_waste_vendus_automatically()
        self.waste_vendus_price = self.calculate_waste_vendus_price_automatically()
        self.waste_non_vendus_kg = self.calculate_waste_non_vendus()

        if not self.end_time:
            start_time = self.created_at if self.created_at else timezone.now()
            self.end_time = start_time + timedelta(minutes=self.estimation_time)

        logger.info(
            f"Product save - Quality: {self.quality}, Price: {self.price}, "
            f"Quantity: {self.quantity}kg, Olive Oil Volume: {self.olive_oil_volume}L, "
            f"Total Waste: {self.total_waste_kg}kg, "
            f"Waste Vendus: {self.waste_vendus_kg}kg ({self.get_waste_vendus_percentage():.1f}%), "
            f"Waste Non Vendus: {self.waste_non_vendus_kg}kg, "
            f"Waste Revenue: {self.waste_vendus_price}DT"
        )

        super().save(*args, **kwargs)

        logger.info(f"Product {self.id} saved successfully with automatic waste calculations")

    def __str__(self):
        return f"Product {self.id} - {self.get_status_display()} ({self.quantity}kg → {self.olive_oil_volume}L, Waste: {self.waste_vendus_kg}kg sold)"

    class Meta:
        ordering = ['end_time']
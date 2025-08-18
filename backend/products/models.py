from django.db import migrations
from rest_framework import serializers
from django.db import models, transaction
from users.models import CustomUser
from django.utils import timezone
from datetime import timedelta
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from factures.models import Facture
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
        default=Decimal('0'),  # FIXÉ: Utilise Decimal au lieu de 0
        help_text="Sold waste in kg"
    )

    waste_non_vendus_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Unsold waste in kg"
    )

    waste_vendus_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0'),  # FIXÉ: Utilise Decimal au lieu de 0
        help_text="Revenue from sold waste in DT"
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

    def calculate_waste_non_vendus(self):
        """Calculate unsold waste"""
        if self.total_waste_kg:
            # FIXÉ: Assurer que waste_vendus_kg est Decimal
            waste_vendus = self.waste_vendus_kg or Decimal('0')
            if isinstance(waste_vendus, (int, float)):
                waste_vendus = Decimal(str(waste_vendus))
            return self.total_waste_kg - waste_vendus
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
        if self.total_waste_kg and self.total_waste_kg > 0:
            # FIXÉ: Assurer que waste_vendus_kg est Decimal
            waste_vendus = self.waste_vendus_kg or Decimal('0')
            if isinstance(waste_vendus, (int, float)):
                waste_vendus = Decimal(str(waste_vendus))
            percentage = (waste_vendus / self.total_waste_kg) * Decimal('100')
            return float(percentage)
        return 0.0

    def sell_waste(self, quantity_sold, price_per_kg):
        """Mark some waste as sold"""
        # FIXÉ: Convertir les entrées en Decimal
        quantity_sold = Decimal(str(quantity_sold))
        price_per_kg = Decimal(str(price_per_kg))

        current_vendus = self.waste_vendus_kg or Decimal('0')
        if isinstance(current_vendus, (int, float)):
            current_vendus = Decimal(str(current_vendus))

        if current_vendus + quantity_sold <= self.total_waste_kg:
            self.waste_vendus_kg = current_vendus + quantity_sold

            current_price = self.waste_vendus_price or Decimal('0')
            if isinstance(current_price, (int, float)):
                current_price = Decimal(str(current_price))

            self.waste_vendus_price = current_price + \
                (quantity_sold * price_per_kg)
            self.waste_non_vendus_kg = self.calculate_waste_non_vendus()
            self.save()
            return True
        return False

    def save(self, *args, **kwargs):
        """Calculate price, olive oil volume, and waste amounts"""
        logger.info(
            f"Saving product {self.id if self.id else 'new'} - Status: {self.status}, Quality: {self.quality}"
        )

        # FIXÉ: Calculate price based on quality using Decimal
        base_price = self.QUALITY_PRICE_MAP.get(self.quality, Decimal('10'))
        self.price = base_price * Decimal(str(self.quantity))

        # Calculate olive oil volume
        self.olive_oil_volume = self.calculate_olive_oil_volume()

        # Calculate waste amounts
        self.total_waste_kg = self.calculate_total_waste()
        self.waste_non_vendus_kg = self.calculate_waste_non_vendus()

        # FIXÉ: Assurer que les champs Decimal sont bien des Decimal
        if self.waste_vendus_kg is not None and not isinstance(self.waste_vendus_kg, Decimal):
            self.waste_vendus_kg = Decimal(str(self.waste_vendus_kg))

        if self.waste_vendus_price is not None and not isinstance(self.waste_vendus_price, Decimal):
            self.waste_vendus_price = Decimal(str(self.waste_vendus_price))

        # Calculate end_time if not set
        if not self.end_time:
            start_time = self.created_at if self.created_at else timezone.now()
            self.end_time = start_time + \
                timedelta(minutes=self.estimation_time)
            logger.info(f"Calculated end_time for product: {self.end_time}")

        logger.info(
            f"Product save - Quality: {self.quality}, Price: {self.price}, "
            f"Quantity: {self.quantity}kg, Olive Oil Volume: {self.olive_oil_volume}L, "
            f"Total Waste: {self.total_waste_kg}kg, Vendus: {self.waste_vendus_kg}kg, Non Vendus: {self.waste_non_vendus_kg}kg"
        )

        super().save(*args, **kwargs)

        logger.info(
            f"Product {self.id} saved successfully with status: {self.status}"
        )

    def __str__(self):
        return f"Product {self.id} - {self.get_status_display()} ({self.quantity}kg → {self.olive_oil_volume}L)"

    class Meta:
        ordering = ['end_time']


# serializers.py - Version corrigée


logger = logging.getLogger(__name__)


class ProductSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(
        source='client.username', read_only=True)
    client = serializers.SlugRelatedField(
        queryset=CustomUser.objects.filter(role='CLIENT'),
        slug_field='cin',
        required=True
    )
    created_by = serializers.SlugRelatedField(
        slug_field='username', read_only=True)
    end_time = serializers.DateTimeField(read_only=True)
    olive_oil_volume = serializers.DecimalField(
        max_digits=10, decimal_places=3, read_only=True)
    oil_efficiency_percentage = serializers.SerializerMethodField()
    total_waste_kg = serializers.DecimalField(
        max_digits=10, decimal_places=3, read_only=True)
    waste_vendus_kg = serializers.DecimalField(
        max_digits=10, decimal_places=3, read_only=True)
    waste_non_vendus_kg = serializers.DecimalField(
        max_digits=10, decimal_places=3, read_only=True)
    waste_vendus_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True)
    waste_percentage = serializers.SerializerMethodField()
    waste_vendus_percentage = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'quality', 'origine', 'price',
            'quantity', 'olive_oil_volume', 'oil_efficiency_percentage',
            'total_waste_kg', 'waste_vendus_kg', 'waste_non_vendus_kg',
            'waste_vendus_price', 'waste_percentage', 'waste_vendus_percentage',
            'client', 'client_name', 'status', 'created_by',
            'created_at', 'estimation_time', 'end_time', 'payement'
        ]
        read_only_fields = [
            'created_by', 'created_at', 'client_name', 'end_time',
            'olive_oil_volume', 'oil_efficiency_percentage',
            'total_waste_kg', 'waste_vendus_kg', 'waste_non_vendus_kg',
            'waste_vendus_price', 'waste_percentage', 'waste_vendus_percentage'
        ]

    def get_oil_efficiency_percentage(self, obj):
        return obj.get_oil_efficiency_percentage()

    def get_waste_percentage(self, obj):
        return obj.get_waste_percentage()

    def get_waste_vendus_percentage(self, obj):
        return obj.get_waste_vendus_percentage()

    def validate_client(self, value):
        if value.role != 'CLIENT':
            raise serializers.ValidationError(
                "The client must have the 'CLIENT' role.")
        return value

    def validate_estimation_time(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Estimation time must be greater than 0 minutes.")
        return value

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        if 'estimation_time' not in validated_data:
            validated_data['estimation_time'] = validated_data.get(
                'quantity', 1) * 30
        return super().create(validated_data)

    def update(self, instance, validated_data):
        """FIXÉ: Update avec gestion correcte des types Decimal"""
        logger.info(
            f"Updating product {instance.id} with data: {validated_data}")

        old_status = instance.status
        new_status = validated_data.get('status', old_status)

        if 'estimation_time' in validated_data and validated_data['estimation_time'] != instance.estimation_time:
            instance.end_time = None
            logger.info(
                f"Estimation time changed, resetting end_time for product {instance.id}")

        if old_status != 'done' and new_status == 'done':
            validated_data['end_time'] = timezone.now()
            logger.info(
                f"Status changed to 'done', setting end_time to now for product {instance.id}")

        # FIXÉ: Convertir les valeurs numériques en Decimal si nécessaire
        for field in ['price', 'waste_vendus_kg', 'waste_vendus_price']:
            if field in validated_data and validated_data[field] is not None:
                if not isinstance(validated_data[field], Decimal):
                    validated_data[field] = Decimal(str(validated_data[field]))

        updated_instance = super().update(instance, validated_data)

        logger.info(
            f"Product {instance.id} updated successfully. Status: {updated_instance.status}, "
            f"Payment: {updated_instance.payement}, Oil Volume: {updated_instance.olive_oil_volume}L")

        return updated_instance


# Migration pour corriger les données existantes (si nécessaire)
# XXXX_fix_decimal_types.py


def fix_decimal_fields(apps, schema_editor):
    """Corriger les champs Decimal qui pourraient être None ou float"""
    Product = apps.get_model('products', 'Product')

    for product in Product.objects.all():
        changed = False

        if product.waste_vendus_kg is None:
            product.waste_vendus_kg = Decimal('0')
            changed = True

        if product.waste_vendus_price is None:
            product.waste_vendus_price = Decimal('0')
            changed = True

        if changed:
            product.save(update_fields=[
                         'waste_vendus_kg', 'waste_vendus_price'])


def reverse_fix_decimal_fields(apps, schema_editor):
    pass  # Ne rien faire en cas de rollback


class Migration(migrations.Migration):
    dependencies = [
        # Remplacez par votre dernière migration
        ('products', 'previous_migration'),
    ]

    operations = [
        migrations.RunPython(fix_decimal_fields, reverse_fix_decimal_fields),
    ]

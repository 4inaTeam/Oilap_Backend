from rest_framework import serializers
from .models import Product
from users.models import CustomUser
from django.utils import timezone
from decimal import Decimal
import logging

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

    waste_price_per_kg = serializers.SerializerMethodField()
    waste_sold_percentage_rule = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'quality', 'origine', 'price',
            'quantity', 'olive_oil_volume', 'oil_efficiency_percentage',
            'total_waste_kg', 'waste_vendus_kg', 'waste_non_vendus_kg',
            'waste_vendus_price', 'waste_percentage', 'waste_vendus_percentage',
            'waste_price_per_kg', 'waste_sold_percentage_rule',
            'client', 'client_name', 'status', 'created_by',
            'created_at', 'estimation_time', 'end_time', 'payement'
        ]
        read_only_fields = [
            'created_by', 'created_at', 'client_name', 'end_time',
            'olive_oil_volume', 'oil_efficiency_percentage',
            'total_waste_kg', 'waste_vendus_kg', 'waste_non_vendus_kg',
            'waste_vendus_price', 'waste_percentage', 'waste_vendus_percentage',
            'waste_price_per_kg', 'waste_sold_percentage_rule'
        ]

    def get_oil_efficiency_percentage(self, obj):
        return obj.get_oil_efficiency_percentage()

    def get_waste_percentage(self, obj):
        return obj.get_waste_percentage()

    def get_waste_vendus_percentage(self, obj):
        return obj.get_waste_vendus_percentage()

    def get_waste_price_per_kg(self, obj):
        """Show the price per kg used for this quality"""
        return float(obj.WASTE_PRICE_PER_KG.get(obj.quality, Decimal('4.00')))

    def get_waste_sold_percentage_rule(self, obj):
        """Show the percentage rule used for this quality"""
        percentage = obj.WASTE_SOLD_PERCENTAGE.get(
            obj.quality, Decimal('0.50'))
        return float(percentage * 100)

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

        logger.info(f"Creating product with automatic waste calculation")
        return super().create(validated_data)

    def update(self, instance, validated_data):
        """Update with automatic waste recalculation"""
        logger.info(
            f"Updating product {instance.id} - waste will be recalculated automatically")

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

        updated_instance = super().update(instance, validated_data)

        logger.info(
            f"Product {updated_instance.id} updated with automatic calculations:"
            f"\n  Quality: {updated_instance.quality}"
            f"\n  Quantity: {updated_instance.quantity}kg"
            f"\n  Total Waste: {updated_instance.total_waste_kg}kg"
            f"\n  Waste Vendus: {updated_instance.waste_vendus_kg}kg ({updated_instance.get_waste_vendus_percentage():.1f}%)"
            f"\n  Waste Price: {updated_instance.waste_vendus_price}DT"
            f"\n  Waste Non Vendus: {updated_instance.waste_non_vendus_kg}kg"
        )

        return updated_instance


class ProductSummarySerializer(serializers.ModelSerializer):
    """Simplified serializer for lists and summaries"""
    client_name = serializers.CharField(
        source='client.username', read_only=True)
    waste_vendus_percentage = serializers.SerializerMethodField()
    total_revenue = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'quality', 'quantity', 'price', 'status',
            'client_name', 'total_waste_kg', 'waste_vendus_kg',
            'waste_vendus_price', 'waste_vendus_percentage', 'total_revenue',
            'created_at', 'end_time'
        ]

    def get_waste_vendus_percentage(self, obj):
        return obj.get_waste_vendus_percentage()

    def get_total_revenue(self, obj):
        """Total revenue from olive oil + waste"""
        oil_revenue = obj.price or Decimal('0')
        waste_revenue = obj.waste_vendus_price or Decimal('0')
        return float(oil_revenue + waste_revenue)

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
        """Enhanced update method with proper waste calculation when status becomes 'done'"""
        logger.info(
            f"Updating product {instance.id} with data: {validated_data}")

        old_status = instance.status
        new_status = validated_data.get('status', old_status)

        # Reset end_time if estimation_time changes
        if 'estimation_time' in validated_data and validated_data['estimation_time'] != instance.estimation_time:
            instance.end_time = None
            logger.info(
                f"Estimation time changed, resetting end_time for product {instance.id}")

        # Handle status change to 'done'
        if old_status != 'done' and new_status == 'done':
            validated_data['end_time'] = timezone.now()
            logger.info(
                f"Status changed to 'done', setting end_time to now for product {instance.id}")

            # Force recalculation of waste when product is done
            # The model's save() method will handle the calculations, but we ensure it's triggered
            logger.info(
                f"Product {instance.id} is being marked as done - waste will be recalculated")

        # Convert numeric fields to Decimal if necessary
        for field in ['price', 'waste_vendus_kg', 'waste_vendus_price']:
            if field in validated_data and validated_data[field] is not None:
                if not isinstance(validated_data[field], Decimal):
                    validated_data[field] = Decimal(str(validated_data[field]))

        # Update the instance
        updated_instance = super().update(instance, validated_data)

        # Log the waste calculations after update
        if new_status == 'done':
            logger.info(
                f"Product {updated_instance.id} marked as done. "
                f"Quality: {updated_instance.quality}, "
                f"Quantity: {updated_instance.quantity}kg, "
                f"Olive Oil Volume: {updated_instance.olive_oil_volume}L, "
                f"Total Waste: {updated_instance.total_waste_kg}kg, "
                f"Waste Vendus: {updated_instance.waste_vendus_kg}kg, "
                f"Waste Non Vendus: {updated_instance.waste_non_vendus_kg}kg, "
                f"Waste Revenue: {updated_instance.waste_vendus_price}DT"
            )

        logger.info(
            f"Product {updated_instance.id} updated successfully. "
            f"Status: {updated_instance.status}, "
            f"Payment: {updated_instance.payement}")

        return updated_instance


# Optional: Add a specific method to manually trigger waste recalculation
class WasteCalculationMixin:
    """Mixin to add waste calculation methods to serializers"""

    def recalculate_waste(self, instance):
        """Manually recalculate waste for a product instance"""
        logger.info(f"Manually recalculating waste for product {instance.id}")

        # The model's save method will handle all calculations
        instance.save()

        logger.info(
            f"Waste recalculated for product {instance.id}: "
            f"Total: {instance.total_waste_kg}kg, "
            f"Vendus: {instance.waste_vendus_kg}kg, "
            f"Non Vendus: {instance.waste_non_vendus_kg}kg"
        )

        return instance


# Enhanced serializer with waste calculation mixin
class EnhancedProductSerializer(ProductSerializer, WasteCalculationMixin):
    """Enhanced product serializer with additional waste calculation capabilities"""

    def update(self, instance, validated_data):
        updated_instance = super().update(instance, validated_data)

        # If status changed to done, ensure waste is properly calculated
        new_status = validated_data.get('status')
        if new_status == 'done':
            # Force a recalculation to ensure all waste fields are up to date
            self.recalculate_waste(updated_instance)

        return updated_instance


# Alternative: Status-specific serializer for done products
class DoneProductSerializer(serializers.ModelSerializer):
    """Specialized serializer for products with 'done' status that includes waste details"""

    client_name = serializers.CharField(
        source='client.username', read_only=True)
    oil_efficiency_percentage = serializers.SerializerMethodField()
    waste_percentage = serializers.SerializerMethodField()
    waste_vendus_percentage = serializers.SerializerMethodField()
    waste_breakdown = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'quality', 'origine', 'price', 'quantity',
            'olive_oil_volume', 'oil_efficiency_percentage',
            'total_waste_kg', 'waste_vendus_kg', 'waste_non_vendus_kg',
            'waste_vendus_price', 'waste_percentage', 'waste_vendus_percentage',
            'waste_breakdown', 'client', 'client_name', 'status',
            'created_at', 'end_time', 'payement'
        ]
        read_only_fields = ['status']  # Prevent changing status from 'done'

    def get_oil_efficiency_percentage(self, obj):
        return obj.get_oil_efficiency_percentage()

    def get_waste_percentage(self, obj):
        return obj.get_waste_percentage()

    def get_waste_vendus_percentage(self, obj):
        return obj.get_waste_vendus_percentage()

    def get_waste_breakdown(self, obj):
        """Provide detailed waste breakdown"""
        if not obj.total_waste_kg:
            return {
                'total_waste_kg': 0,
                'waste_vendus_kg': 0,
                'waste_non_vendus_kg': 0,
                'waste_vendus_price': 0,
                'average_price_per_kg': 0,
                'waste_coefficient_used': obj.WASTE_COEFFICIENTS.get(obj.quality, Decimal('0.85'))
            }

        avg_price = (obj.waste_vendus_price /
                     obj.waste_vendus_kg) if obj.waste_vendus_kg and obj.waste_vendus_kg > 0 else Decimal('0')

        return {
            'total_waste_kg': float(obj.total_waste_kg),
            'waste_vendus_kg': float(obj.waste_vendus_kg or 0),
            'waste_non_vendus_kg': float(obj.waste_non_vendus_kg or 0),
            'waste_vendus_price': float(obj.waste_vendus_price or 0),
            'average_price_per_kg': float(avg_price),
            'waste_coefficient_used': float(obj.WASTE_COEFFICIENTS.get(obj.quality, Decimal('0.85'))),
            'vendus_percentage': obj.get_waste_vendus_percentage(),
            'non_vendus_percentage': 100 - obj.get_waste_vendus_percentage() if obj.get_waste_vendus_percentage() else 0
        }

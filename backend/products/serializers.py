from rest_framework import serializers
from .models import Product
from users.models import CustomUser
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class ProductSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(
        source='client.username',
        read_only=True
    )

    client = serializers.SlugRelatedField(
        queryset=CustomUser.objects.filter(role='CLIENT'),
        slug_field='cin',
        required=True
    )

    created_by = serializers.SlugRelatedField(
        slug_field='username',
        read_only=True
    )

    # Display end_time as read-only (calculated automatically)
    end_time = serializers.DateTimeField(read_only=True)

    # Display olive oil volume as read-only (calculated automatically)
    olive_oil_volume = serializers.DecimalField(
        max_digits=10,
        decimal_places=3,
        read_only=True
    )

    # Display oil efficiency percentage as read-only
    oil_efficiency_percentage = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'quality', 'origine', 'price',
            'quantity', 'olive_oil_volume', 'oil_efficiency_percentage',
            'client', 'client_name', 'status', 'created_by',
            'created_at', 'estimation_time', 'end_time', 'payement'
        ]
        read_only_fields = [
            'created_by', 'created_at', 'client_name', 'end_time',
            'olive_oil_volume', 'oil_efficiency_percentage'
        ]

    def get_oil_efficiency_percentage(self, obj):
        """Get the oil extraction efficiency as a percentage"""
        return obj.get_oil_efficiency_percentage()

    def validate_client(self, value):
        if value.role != 'CLIENT':
            raise serializers.ValidationError(
                "The client must have the 'CLIENT' role.")
        return value

    def validate_estimation_time(self, value):
        """Validate estimation_time is positive"""
        if value <= 0:
            raise serializers.ValidationError(
                "Estimation time must be greater than 0 minutes.")
        return value

    def create(self, validated_data):
        """Create product with automatic end_time calculation"""
        validated_data['created_by'] = self.context['request'].user

        # If no estimation_time provided, calculate based on quantity
        if 'estimation_time' not in validated_data:
            validated_data['estimation_time'] = validated_data.get(
                'quantity', 1) * 30  # 30 min per unit

        # The model's save() method will handle end_time and olive_oil_volume calculation
        return super().create(validated_data)

    def update(self, instance, validated_data):
        """Update product and handle end_time recalculation properly"""
        logger.info(
            f"Updating product {instance.id} with data: {validated_data}")

        # Store original values for comparison
        old_status = instance.status
        new_status = validated_data.get('status', old_status)

        # If estimation_time is being changed, reset end_time
        if 'estimation_time' in validated_data and validated_data['estimation_time'] != instance.estimation_time:
            instance.end_time = None
            logger.info(
                f"Estimation time changed, resetting end_time for product {instance.id}")

        # If status is being changed to 'done', set end_time to now
        if old_status != 'done' and new_status == 'done':
            validated_data['end_time'] = timezone.now()
            logger.info(
                f"Status changed to 'done', setting end_time to now for product {instance.id}")

        # Update the instance (olive_oil_volume will be recalculated automatically in save())
        updated_instance = super().update(instance, validated_data)

        logger.info(
            f"Product {instance.id} updated successfully. Status: {updated_instance.status}, "
            f"Payment: {updated_instance.payement}, Oil Volume: {updated_instance.olive_oil_volume}L")

        return updated_instance

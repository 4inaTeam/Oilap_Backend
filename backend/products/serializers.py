from rest_framework import serializers
from .models import Product
from users.models import CustomUser
from django.utils import timezone
from datetime import timedelta


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
    
    class Meta:
        model = Product
        fields = [
            'id', 'quality', 'origine', 'price',
            'quantity', 'client', 'client_name', 'status', 'created_by',
            'created_at', 'photo', 'estimation_time', 'end_time'
        ]
        read_only_fields = [
            'created_by', 'created_at', 'client_name', 'end_time'
        ]

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
            validated_data['estimation_time'] = validated_data.get('quantity', 1) * 30  # 30 min per unit
        
        # The model's save() method will handle end_time calculation
        return super().create(validated_data)

    def update(self, instance, validated_data):
        """Update product and recalculate end_time if estimation_time changes"""
        if 'estimation_time' in validated_data:
            # Reset end_time so it gets recalculated in save()
            instance.end_time = None
        
        return super().update(instance, validated_data)
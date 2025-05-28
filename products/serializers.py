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

    class Meta:
        model = Product
        fields = [
            'id', 'quality', 'origine', 'price',
            'quantity', 'client', 'client_name', 'status', 'created_by',  # Add 'client' here
            'created_at', 'photo', 'estimation_date'
        ]
        read_only_fields = [
            'created_by', 'created_at',
            'estimation_date', 'client_name'
        ]

    def validate_client(self, value):
        if value.role != 'CLIENT':
            raise serializers.ValidationError(
                "The client must have the 'CLIENT' role.")
        return value

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user

        latest_product = Product.objects.filter(
            status__in=['pending', 'doing']).order_by('-estimation_date').first()
            
        start_time = latest_product.estimation_date if latest_product else timezone.now()
        processing_hours = validated_data['quantity'] * 0.5
        validated_data['estimation_date'] = start_time + timedelta(hours=processing_hours)

        return super().create(validated_data)
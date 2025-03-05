from rest_framework import serializers
from .models import Product
from clients.models import Client

class ProductSerializer(serializers.ModelSerializer):
    status = serializers.ChoiceField(choices=Product.STATUS_CHOICES, required=False)

    class Meta:
        model = Product
        fields = ['id', 'name', 'quality', 'origine', 'price', 'client', 'created_by', 'created_at', 'status']

class ProductWithClientSerializer(serializers.Serializer):
    # Fields for the client
    client_name = serializers.CharField(max_length=100)
    client_email = serializers.EmailField()
    client_cin = serializers.CharField(max_length=15, required=False, allow_blank=True)

    # Fields for the product
    product_name = serializers.CharField(max_length=100)
    product_quality = serializers.CharField(required=False, allow_blank=True)
    product_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    product_origine = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=Product.STATUS_CHOICES, required=False, default='pending')

    def create(self, validated_data):
        # Get the employee (created_by)
        employee = self.context['request'].user

        # Check if the client already exists
        client_email = validated_data['client_email']
        client, created = Client.objects.get_or_create(
            email=client_email,
            defaults={
                'name': validated_data['client_name'],
                'cin': validated_data.get('client_cin', ''),
                'created_by': employee,
            }
        )

        # Create the product
        product = Product.objects.create(
            name=validated_data['product_name'],
            quality=validated_data.get('product_quality', ''),
            price=validated_data['product_price'],
            origine=validated_data.get('product_origine', ''),
            client=client,
            created_by=employee,
            status=validated_data.get('status', 'pending'),
        )

        return product

    def to_representation(self, instance):
        # Use ProductSerializer for output
        return ProductSerializer(instance).data

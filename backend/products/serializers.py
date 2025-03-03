# products/serializers.py
from rest_framework import serializers
from .models import Product
from clients.models import Client  # Import Client from the clients app

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name', 'quality', 'price', 'client', 'created_by', 'created_at']
        
class ProductWithClientSerializer(serializers.Serializer):
    # Fields for the client
    client_name = serializers.CharField(max_length=100)
    client_email = serializers.EmailField()
    client_cin = serializers.CharField(max_length=15, required=False, allow_blank=True)

    # Fields for the product
    product_name = serializers.CharField(max_length=100)
    product_quality = serializers.CharField(required=False, allow_blank=True)
    product_price = serializers.DecimalField(max_digits=10, decimal_places=2)

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
            quality=validated_data.get('product_quality', ''),  # <-- Fixed here
            price=validated_data['product_price'],
            client=client,
            created_by=employee,
        )

        return product

    def to_representation(self, instance):
        # Use ProductSerializer for output
        return ProductSerializer(instance).data
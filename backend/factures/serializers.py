from rest_framework import serializers
from .models import Facture
from users.serializers import CustomUserSerializer
from products.serializers import ProductSerializer

class FactureSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    client = serializers.StringRelatedField(source='client.custom_user.username')
    employee = CustomUserSerializer(read_only=True)
    accountant = CustomUserSerializer(read_only=True)
    
    class Meta:
        model = Facture
        fields = [
            'id', 'product', 'client', 'employee', 'accountant',
            'base_amount', 'tax_amount', 'total_amount',
            'issue_date', 'due_date', 'status', 'payment_date'
        ]
        read_only_fields = [
            'base_amount', 'tax_amount', 'total_amount',
            'issue_date', 'employee', 'accountant'
        ]

class FactureStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Facture
        fields = ['status', 'payment_date']
        extra_kwargs = {
            'payment_date': {'read_only': True}
        }
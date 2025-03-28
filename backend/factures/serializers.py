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
            'issue_date', 'due_date', 'status', 'payment_date',
            'qr_code','payment_uuid', 'qr_verified', 'created_at'
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

class QRCodeValidationSerializer(serializers.Serializer):
    qr_data = serializers.JSONField()
    
    def validate_qr_data(self, value):
        required_fields = ['facture_id', 'uuid', 'amount', 'currency']
        if not all(field in value for field in required_fields):
            raise serializers.ValidationError("QR code invalide")
        return value

class QRCodePaymentSerializer(serializers.Serializer):
    facture_id = serializers.IntegerField()
    payment_uuid = serializers.UUIDField()
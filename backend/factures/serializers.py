from rest_framework import serializers
from .models import Facture
from users.serializers import CustomUserSerializer
from products.serializers import ProductSerializer

class FactureSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    client = serializers.StringRelatedField(source='client.username')  # Updated to direct username
    employee = CustomUserSerializer(read_only=True)
    accountant = CustomUserSerializer(read_only=True)
    qr_code = serializers.SerializerMethodField()  # Add custom method for full URL

    class Meta:
        model = Facture
        fields = [
            'id', 'product', 'client', 'employee', 'accountant',
            'base_amount', 'tax_amount', 'total_amount',
            'issue_date', 'due_date', 'status', 'payment_date',
            'qr_code', 'payment_uuid', 'qr_verified', 'created_at'
        ]
        read_only_fields = [
            'base_amount', 'tax_amount', 'total_amount',
            'issue_date', 'employee', 'accountant'
        ]

    def get_qr_code(self, obj):
        if obj.qr_code:
            return self.context['request'].build_absolute_uri(obj.qr_code.url)
        return None

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

# factures/serializers.py
class FactureCreateSerializer(serializers.ModelSerializer):
    due_date = serializers.DateField()
    base_amount = serializers.DecimalField(  # Explicitly define base_amount
        max_digits=10,
        decimal_places=2,
        required=False,
        allow_null=True
    )

    class Meta:
        model = Facture
        fields = [
            'type', 'product', 'client', 'base_amount', 
            'due_date', 'tax_amount', 'total_amount'
        ]
        extra_kwargs = {
            'product': {'required': False},
            'client': {'required': False},
            'tax_amount': {'read_only': True},
            'total_amount': {'read_only': True}
        }

    def validate(self, attrs):
        facture_type = attrs.get('type')
        if facture_type != 'CLIENT':
            attrs.pop('product', None)
            attrs.pop('client', None)
            if 'base_amount' not in attrs:
                raise serializers.ValidationError({"base_amount": "Required for non-client factures"})
        return attrs
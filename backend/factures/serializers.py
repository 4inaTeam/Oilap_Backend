from rest_framework import serializers
from .models import Facture
from users.serializers import CustomUserSerializer
from products.serializers import ProductSerializer

from rest_framework import serializers
from django.utils import timezone
from .models import Facture
from products.serializers import ProductSerializer
from users.serializers import CustomUserSerializer

class FactureSerializer(serializers.ModelSerializer):
    type = serializers.ChoiceField(choices=Facture.TYPE_CHOICES, read_only=True)
    
    product    = ProductSerializer(read_only=True)
    client     = serializers.SlugRelatedField(
                     read_only=True,
                     slug_field='username'
                 )
    employee   = CustomUserSerializer(read_only=True)
    accountant = CustomUserSerializer(read_only=True)

    qr_code_url = serializers.SerializerMethodField()
    image_url   = serializers.SerializerMethodField()
    pdf_url     = serializers.SerializerMethodField()

    base_amount  = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    tax_amount   = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    issue_date   = serializers.DateField(format='%Y-%m-%d', read_only=True)
    due_date     = serializers.DateField(format='%Y-%m-%d', read_only=True)
    payment_date = serializers.DateTimeField(format='%Y-%m-%dT%H:%M:%SZ', read_only=True)

    payment_uuid = serializers.UUIDField(read_only=True)
    qr_verified  = serializers.BooleanField(read_only=True)

    class Meta:
        model = Facture
        fields = [
            'id', 'type', 'product', 'client', 'employee', 'accountant',
            'base_amount', 'tax_amount', 'total_amount',
            'issue_date', 'due_date', 'status', 'payment_date',
            'payment_uuid', 'qr_verified',
            'qr_code_url', 'image_url', 'pdf_url',
        ]

    def get_qr_code_url(self, obj):
        if obj.qr_code:
            return self.context['request'].build_absolute_uri(obj.qr_code.url)
        return None

    def get_image_url(self, obj):
        if obj.image:
            return self.context['request'].build_absolute_uri(obj.image.url)
        return None

    def get_pdf_url(self, obj):
        if obj.pdf_file:
            return self.context['request'].build_absolute_uri(obj.pdf_file.url)
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

class FactureCreateSerializer(serializers.ModelSerializer):
    due_date     = serializers.DateField(required=False, allow_null=True)
    image        = serializers.ImageField(required=False, allow_null=True)
    base_amount  = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)

    class Meta:
        model  = Facture
        fields = [
            'type', 'product', 'client', 'base_amount',
            'due_date', 'tax_amount', 'total_amount', 'image'
        ]
        extra_kwargs = {
            'product':      {'required': False},
            'client':       {'required': False},
            'tax_amount':   {'read_only': True},
            'total_amount': {'read_only': True},
        }

    def validate(self, attrs):
        facture_type = attrs.get('type')

        if facture_type != 'CLIENT':
            # image et montant de base sont obligatoires
            if not attrs.get('image'):
                raise serializers.ValidationError(
                    {"image": "Image is required for non-client factures."}
                )
            if 'base_amount' not in attrs:
                raise serializers.ValidationError(
                    {"base_amount": "Base amount is required for non-client factures."}
                )
            # on ne poppe plus 'base_amount' pour le conserver
            attrs.pop('product', None)
            attrs.pop('client', None)

        else:
            if not attrs.get('product'):
                raise serializers.ValidationError(
                    {"product": "Product is required for client factures."}
                )
        return attrs
from rest_framework import serializers
from .models import Facture
from products.models import Product


class FactureProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'quality', 'quantity',
                  'price', 'origine', 'status', 'payement']


class FactureSerializer(serializers.ModelSerializer):
    products = FactureProductSerializer(many=True, read_only=True)
    client_name = serializers.CharField(
        source='client.username', read_only=True)
    client_email = serializers.CharField(source='client.email', read_only=True)

    class Meta:
        model = Facture
        fields = [
            'id', 'facture_number', 'client', 'client_name', 'client_email',
            'created_at', 'updated_at', 'payment_status', 'total_amount',
            'tva_rate', 'tva_amount', 'credit_card_fee', 'final_total',
            'stripe_payment_intent', 'pdf_url', 'pdf_public_id', 'products'
        ]
        read_only_fields = ['facture_number', 'total_amount',
                            'tva_amount', 'final_total', 'pdf_url', 'pdf_public_id']

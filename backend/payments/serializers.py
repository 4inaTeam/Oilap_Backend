from rest_framework import serializers
from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    facture_number = serializers.CharField(
        source='facture.facture_number', read_only=True)
    client_name = serializers.CharField(
        source='facture.client.username', read_only=True)

    class Meta:
        model = Payment
        fields = [
            'id', 'facture', 'facture_number', 'client_name', 'amount',
            'payment_method', 'status', 'stripe_payment_intent_id',
            'transaction_reference', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

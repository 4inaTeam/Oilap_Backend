from rest_framework import serializers
from .models import Payment

class PaymentIntentSerializer(serializers.Serializer):
    facture_id = serializers.IntegerField(required=True)
    return_url = serializers.URLField(required=False, allow_null=True)

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = '__all__'
        read_only_fields = ['stripe_payment_intent', 'status']
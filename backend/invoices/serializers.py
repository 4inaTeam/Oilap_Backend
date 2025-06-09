from rest_framework import serializers

class InvoiceResultSerializer(serializers.Serializer):
    filename = serializers.CharField()
    category = serializers.CharField()
    confidence = serializers.FloatField()
    pay_date = serializers.CharField(allow_null=True)
    montant = serializers.CharField(allow_null=True)

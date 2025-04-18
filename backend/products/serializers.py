from rest_framework import serializers
from .models import Product
from users.models import Client

class ProductSerializer(serializers.ModelSerializer):
    client = serializers.SlugRelatedField(
        queryset=Client.objects.all(),
        slug_field='cin',
        required=True
    )

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'quality', 'origine', 'price', 
            'quantity', 'client', 'status', 'created_by', 'created_at', 'photo'
        ]
        read_only_fields = ['created_by', 'created_at']
    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)
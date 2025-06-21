from rest_framework import serializers
from .models import Bill
import json


class BillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bill
        fields = '__all__'
        read_only_fields = ('user', 'pdf_file')

    def validate(self, data):
        category = data.get('category')
        consumption = data.get('consumption')
        items = data.get('items')

        if category in ['water', 'electricity']:
            if consumption is None:
                raise serializers.ValidationError(
                    "Consumption is required for water/electricity bills"
                )
            if items:
                raise serializers.ValidationError(
                    "Items should not be provided for water/electricity bills"
                )

        elif category == 'purchase':
            if not items:
                raise serializers.ValidationError(
                    "Items list is required for purchase bills"
                )
            try:
                json.loads(items)  # Validate JSON format
            except json.JSONDecodeError:
                raise serializers.ValidationError(
                    "Invalid JSON format for items")

        return data

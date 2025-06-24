# bills/serializers.py
from rest_framework import serializers
from .models import Bill, Item  # Updated import

class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = ('id', 'title', 'quantity', 'unit_price')

class BillSerializer(serializers.ModelSerializer):
    items = ItemSerializer(many=True, required=False)  # Nested serializer

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
            # Validate each item
            for item in items:
                if not all(key in item for key in ['title', 'quantity', 'unit_price']):
                    raise serializers.ValidationError(
                        "Each item must contain title, quantity and unit_price"
                    )
        return data

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        bill = Bill.objects.create(**validated_data)
        for item_data in items_data:
            Item.objects.create(bill=bill, **item_data)
        return bill

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        
        # Update bill fields
        instance = super().update(instance, validated_data)
        
        # Handle items update
        if items_data is not None:
            # Delete existing items
            instance.items.all().delete()
            # Create new items
            for item_data in items_data:
                Item.objects.create(bill=instance, **item_data)
        return instance

# Updated BillUpdateSerializer with items support
class BillUpdateSerializer(serializers.ModelSerializer):
    items = ItemSerializer(many=True, required=False)

    class Meta:
        model = Bill
        fields = [
            'owner',
            'category',
            'amount',
            'payment_date',
            'consumption',
            'items'
        ]

    def validate(self, data):
        instance = getattr(self, 'instance', None)
        category = data.get('category', instance.category if instance else None)
        consumption = data.get('consumption')
        items = data.get('items')

        if category in ['water', 'electricity']:
            if 'consumption' in data and consumption is None:
                raise serializers.ValidationError(
                    "Consumption is required for water/electricity bills"
                )
            if 'items' in data and items:
                raise serializers.ValidationError(
                    "Items should not be provided for water/electricity bills"
                )

        elif category == 'purchase':
            if 'items' in data:
                if not items:
                    raise serializers.ValidationError(
                        "Items list cannot be empty for purchase bills"
                    )
                # Validate item structure
                for item in items:
                    if not all(key in item for key in ['title', 'quantity', 'unit_price']):
                        raise serializers.ValidationError(
                            "Each item must contain title, quantity and unit_price"
                        )
        return data

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        
        # Update bill fields
        instance = super().update(instance, validated_data)
        
        # Handle items update if provided
        if items_data is not None:
            instance.items.all().delete()
            for item_data in items_data:
                Item.objects.create(bill=instance, **item_data)
        return instance
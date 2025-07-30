# Updated serializers.py
from rest_framework import serializers
from .models import Bill, Item
from django.contrib.auth import get_user_model

User = get_user_model()


class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = ('id', 'title', 'quantity', 'unit_price')


class UserInfoSerializer(serializers.ModelSerializer):
    """Serializer to show basic user info in bill responses"""
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name')
        if hasattr(User, 'role'):
            fields += ('role',)


class BillSerializer(serializers.ModelSerializer):
    items = ItemSerializer(many=True, required=False)  # Nested serializer
    user_info = UserInfoSerializer(
        source='user', read_only=True)  # Add user info

    class Meta:
        model = Bill
        fields = '__all__'
        read_only_fields = ('user', 'pdf_file', 'user_info')

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
            # Check if items is None, empty list, or missing
            if not items or len(items) == 0:
                raise serializers.ValidationError(
                    "Items list is required for purchase bills"
                )

            # Validate each item
            for i, item in enumerate(items):
                if not isinstance(item, dict):
                    raise serializers.ValidationError(
                        f"Item {i+1} must be a valid object"
                    )

                required_fields = ['title', 'quantity', 'unit_price']
                missing_fields = [
                    field for field in required_fields if field not in item or not item[field]]

                if missing_fields:
                    raise serializers.ValidationError(
                        f"Item {i+1} is missing required fields: {', '.join(missing_fields)}"
                    )

                # Validate data types
                try:
                    float(item['quantity'])
                    float(item['unit_price'])
                except (ValueError, TypeError):
                    raise serializers.ValidationError(
                        f"Item {i+1} has invalid numeric values for quantity or unit_price"
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
        category = data.get(
            'category', instance.category if instance else None)
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


class BillListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views"""
    items_count = serializers.SerializerMethodField()
    user_info = UserInfoSerializer(source='user', read_only=True)

    class Meta:
        model = Bill
        fields = [
            'id', 'owner', 'category', 'amount', 'payment_date',
            'consumption', 'created_at', 'items_count', 'user_info'
        ]

    def get_items_count(self, obj):
        return obj.items.count() if obj.category == 'purchase' else 0

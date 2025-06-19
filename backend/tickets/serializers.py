from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for Notification model to match Flutter expectations"""

    class Meta:
        model = Notification
        fields = [
            'id',
            'title',
            'body',
            'type',
            'data',
            'created_at',
            'is_read'
        ]

    def to_representation(self, instance):
        """Custom representation to match Flutter NotificationModel structure"""
        data = super().to_representation(instance)

        # Ensure data is always a dict (never null)
        if data['data'] is None:
            data['data'] = {}

        return data

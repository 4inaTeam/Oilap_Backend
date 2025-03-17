from rest_framework import serializers
from .models import CustomUser

class CustomUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'role', 'password']
        extra_kwargs = {
            'password': {'write_only': True},
            'role': {'read_only': True}  # Prevent role manipulation from client side
        }

    def create(self, validated_data):
        # Explicitly set role to CLIENT when creating through ClientCreateView
        validated_data.setdefault('role', 'CLIENT')
        user = CustomUser.objects.create_user(**validated_data)
        return user
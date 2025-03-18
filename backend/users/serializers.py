from rest_framework import serializers
from .models import CustomUser, Client

class CustomUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'role', 'password', 'profile_photo', 'isActive']
        extra_kwargs = {
            'password': {'write_only': True},
            'role': {'read_only': True},
        }

    def create(self, validated_data):
        validated_data.setdefault('role', 'CLIENT')
        user = CustomUser.objects.create_user(**validated_data)
        return user

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'profile_photo']
        extra_kwargs = {
            'username': {'required': False},
            'email': {'required': False},
        }

class AdminUserCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'role', 'password']
        extra_kwargs = {
            'password': {'write_only': True},
        }

    def validate_role(self, value):
        valid_roles = ['EMPLOYEE', 'ACCOUNTANT']
        if value not in valid_roles:
            raise serializers.ValidationError(
                f"Invalid role. Allowed roles: {', '.join(valid_roles)}"
            )
        return value

    def create(self, validated_data):
        return CustomUser.objects.create_user(**validated_data)

class UserActiveStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'isActive']
from rest_framework import serializers
from .models import CustomUser, Client
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import exceptions

User = get_user_model()

class EmailCINAuthSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        login_input = attrs.get(self.username_field)
        password = attrs.get('password')

        # Check if input is email or CIN
        if '@' in login_input:
            user = User.objects.filter(email=login_input).first()
        elif login_input.isdigit() and len(login_input) == 8:
            user = User.objects.filter(cin=login_input).first()
        else:
            raise exceptions.AuthenticationFailed('Invalid credentials. Use email or CIN.')

        if user and user.check_password(password):
            if not user.is_active:
                raise exceptions.AuthenticationFailed('User account is disabled.')
            
            data = super().validate(attrs)
            return data

        raise exceptions.AuthenticationFailed('Invalid credentials.')

class CustomUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = [
            'id', 'username', 'email', 'role', 
            'password', 'profile_photo', 'isActive',
            'cin', 'tel'
        ]
        extra_kwargs = {
            'password': {'write_only': True},
            'role': {'read_only': True},
            'cin': {'required': True},
            'tel': {'required': True},
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
        fields = ['id', 'username', 'email', 'role', 'password', 'cin', 'tel']
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
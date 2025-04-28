from rest_framework import serializers, exceptions
from .models import CustomUser, Client
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


User = get_user_model()

class EmailCINAuthSerializer(TokenObtainPairSerializer):
    cin = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        cin_input = attrs.get('cin')
        password = attrs.get('password')

        if '@' in cin_input:
            user = CustomUser.objects.filter(email=cin_input).first()
        elif cin_input.isdigit() and len(cin_input) == 8:
            user = CustomUser.objects.filter(cin=cin_input).first()
        else:
            raise exceptions.AuthenticationFailed('Invalid credentials. Use CIN or email.')

        if user and user.check_password(password):
            if not user.is_active:
                raise exceptions.AuthenticationFailed('User account is disabled.')
            
            refresh = self.get_token(user)
            return {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }

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


class ClientUpdateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'password', 'first_name', 'last_name']  # add any field you want to allow

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance
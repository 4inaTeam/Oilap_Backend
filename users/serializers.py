from rest_framework import serializers, exceptions
from .models import CustomUser, Client
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import serializers, exceptions 



User = get_user_model()

class EmailCINAuthSerializer(serializers.Serializer):
    identifier = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        identifier = attrs.get('identifier')
        password = attrs.get('password')

        user = None

        if '@' in identifier:
            user = CustomUser.objects.filter(email__iexact=identifier).first()
        elif identifier.isdigit() and len(identifier) == 8:
            user = CustomUser.objects.filter(cin=identifier).first()
        else:
            raise exceptions.AuthenticationFailed('Invalid identifier format. Use a valid email or 8-digit CIN.')

        if user and user.check_password(password):
            if not user.is_active:
                raise exceptions.AuthenticationFailed('User account is disabled.')

            refresh = RefreshToken.for_user(user)
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
        fields = ['username', 'email', 'profile_photo', 'tel', 'cin']
        extra_kwargs = {
            'username': {'required': False},
            'email': {'required': False},
            'profile_photo': {'required': False},
            'tel': {'required': False},
            'cin': {'required': False},
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
        fields = ['username', 'email', 'password', 'first_name', 'last_name']

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance
    
class EmployeeAccountantUpdateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'password', 'tel', 'profile_photo', 'role']
        extra_kwargs = {
            'username': {'required': False},
            'email': {'required': False},
            'tel': {'required': False},
            'profile_photo': {'required': False},
        }

    def validate_role(self, value):
        """Ensure only EMPLOYEE or ACCOUNTANT roles can be set"""
        valid_roles = ['EMPLOYEE', 'ACCOUNTANT']
        if value and value not in valid_roles:
            raise serializers.ValidationError(
                f"Invalid role. Allowed roles: {', '.join(valid_roles)}"
            )
        return value

    def validate_email(self, value):
        """Ensure email uniqueness when updating"""
        if value:
            # Exclude current instance from uniqueness check
            queryset = CustomUser.objects.filter(email=value)
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError("A user with this email already exists.")
        return value

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        if password:
            instance.set_password(password)
        
        instance.save()
        return instance

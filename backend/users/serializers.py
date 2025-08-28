from rest_framework import serializers, exceptions
from .models import CustomUser, Client
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.validators import validate_email
from django.core.exceptions import ValidationError as DjangoValidationError
import re


User = get_user_model()


def validate_cin_format(cin):
    """
    Validate CIN format to ensure it's 8 digits and doesn't contain
    eight consecutive identical digits.
    """
    if not cin:
        raise serializers.ValidationError("CIN is required")
    
    # Convert to string in case it's passed as integer
    cin_str = str(cin)
    
    # Check if it's exactly 8 digits
    if not cin_str.isdigit() or len(cin_str) != 8:
        raise serializers.ValidationError("CIN must be exactly 8 digits")
    
    # Check for eight consecutive identical digits
    if len(set(cin_str)) == 1:
        raise serializers.ValidationError("CIN cannot contain eight identical digits")
    
    return cin_str


def validate_email_domain(email):
    """
    Validate email domain against allowed domains.
    Add your allowed domains here.
    """
    allowed_domains = [
        'gmail.com',
        'yahoo.com',
        'outlook.com',
        'hotmail.com',
        'live.com',
        'icloud.com',
        'mail.com',
    ]

    if not email:
        raise serializers.ValidationError("Email is required")

    try:
        validate_email(email)
    except DjangoValidationError:
        raise serializers.ValidationError("Enter a valid email address")

    domain = email.lower().split('@')[1] if '@' in email else ''

    if domain not in allowed_domains:
        raise serializers.ValidationError(
            f"Email domain '{domain}' is not allowed. "
            f"Allowed domains: {', '.join(allowed_domains)}"
        )

    return email


def validate_email_format_strict(email):
    """
    Strict email validation with additional checks
    """
    if not email:
        raise serializers.ValidationError("Email is required")

    # Basic format validation
    try:
        validate_email(email)
    except DjangoValidationError:
        raise serializers.ValidationError("Enter a valid email address")

    # Additional format checks
    email = email.lower().strip()

    # Check for valid email pattern
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        raise serializers.ValidationError("Email format is invalid")

    # Check for consecutive dots
    if '..' in email:
        raise serializers.ValidationError(
            "Email cannot contain consecutive dots")

    # Check for valid characters in local part
    local_part = email.split('@')[0]
    if len(local_part) == 0 or len(local_part) > 64:
        raise serializers.ValidationError(
            "Email local part must be 1-64 characters")

    # Check domain part
    domain_part = email.split('@')[1]
    if len(domain_part) == 0 or len(domain_part) > 255:
        raise serializers.ValidationError(
            "Email domain part must be 1-255 characters")

    return email


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
            raise exceptions.AuthenticationFailed(
                'Invalid identifier format. Use a valid email or 8-digit CIN.')

        if user and user.check_password(password):
            if not user.is_active:
                raise exceptions.AuthenticationFailed(
                    'User account is disabled.')

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
            'cin', 'tel', 'ville'
        ]
        extra_kwargs = {
            'password': {'write_only': True},
            'role': {'read_only': True},
            'cin': {'required': True},
            'tel': {'required': True},
            'ville': {'required': False},  # Optional, will use default
        }

    def validate_email(self, value):
        """Validate email with domain restrictions"""
        if value:
            # Apply strict format validation
            value = validate_email_format_strict(value)
            # Apply domain validation
            value = validate_email_domain(value)

            # Check if email already exists
            if CustomUser.objects.filter(email__iexact=value).exists():
                raise serializers.ValidationError("Email already exists")
        return value

    def validate_cin(self, value):
        """Validate CIN format and uniqueness"""
        if value:
            # Apply format validation
            value = validate_cin_format(value)
            
            # Check if CIN already exists
            if CustomUser.objects.filter(cin=value).exists():
                raise serializers.ValidationError("CIN already exists")
        return value

    def create(self, validated_data):
        validated_data.setdefault('role', 'CLIENT')
        # If ville is not provided, it will use the model's default value
        user = CustomUser.objects.create_user(**validated_data)
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'profile_photo', 'tel', 'cin', 'ville']
        extra_kwargs = {
            'username': {'required': False},
            'email': {'required': False},
            'profile_photo': {'required': False},
            'tel': {'required': False},
            'cin': {'required': False},
            'ville': {'required': False},
        }


class AdminUserCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'role',
                  'password', 'cin', 'tel', 'ville']
        extra_kwargs = {
            'password': {'write_only': True},
            'ville': {'required': False},
        }

    def validate_email(self, value):
        """Validate email with domain restrictions"""
        if value:
            # Apply strict format validation
            value = validate_email_format_strict(value)
            # Apply domain validation
            value = validate_email_domain(value)

            # Check if email already exists
            if CustomUser.objects.filter(email__iexact=value).exists():
                raise serializers.ValidationError("Email already exists")
        return value

    def validate_role(self, value):
        valid_roles = ['EMPLOYEE', 'ACCOUNTANT', 'EXPERT_COMPTABLE']
        if value not in valid_roles:
            raise serializers.ValidationError(
                f"Invalid role. Allowed roles: {', '.join(valid_roles)}"
            )
        return value

    def validate_cin(self, value):
        """Validate CIN format and uniqueness"""
        if value:
            # Apply format validation
            value = validate_cin_format(value)
            
            # Check if CIN already exists
            if CustomUser.objects.filter(cin=value).exists():
                raise serializers.ValidationError("CIN already exists")
        return value

    def validate_ville(self, value):
        """Validate ville field against available choices"""
        if value:
            valid_cities = [choice[0] for choice in CustomUser.VILLE_CHOICES]
            if value not in valid_cities:
                raise serializers.ValidationError(
                    f"Invalid city. Allowed cities: {', '.join(valid_cities)}"
                )
        return value

    def create(self, validated_data):
        # Ensure ville has a default value if not provided
        if 'ville' not in validated_data or not validated_data['ville']:
            validated_data['ville'] = 'Tunis'
        return CustomUser.objects.create_user(**validated_data)


class UserActiveStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'isActive']


class ClientUpdateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'password', 'first_name', 'last_name',
                  'profile_photo', 'cin', 'tel', 'isActive', 'ville']
        extra_kwargs = {
            'username': {'required': False},
            'email': {'required': False},
            'cin': {'required': False},
            'tel': {'required': False},
            'profile_photo': {'required': False},
            'isActive': {'required': False},
            'ville': {'required': False},
        }

    def validate_email(self, value):
        if value:
            # Apply strict format validation
            value = validate_email_format_strict(value)
            # Apply domain validation
            value = validate_email_domain(value)

            # Check if email already exists (excluding current instance)
            queryset = CustomUser.objects.filter(email__iexact=value)
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError("Email already exists")
        return value

    def validate_cin(self, value):
        if value:
            # Apply format validation
            value = validate_cin_format(value)
            
            # Check if CIN already exists (excluding current instance)
            queryset = CustomUser.objects.filter(cin=value)
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError("CIN already exists")
        return value

    def validate_ville(self, value):
        """Validate ville field against available choices"""
        if value:
            valid_cities = [choice[0] for choice in CustomUser.VILLE_CHOICES]
            if value not in valid_cities:
                raise serializers.ValidationError(
                    f"Invalid city. Allowed cities: {', '.join(valid_cities)}"
                )
        return value

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
        fields = ['username', 'email', 'password',
                  'tel', 'profile_photo', 'role', 'ville']
        extra_kwargs = {
            'username': {'required': False},
            'email': {'required': False},
            'tel': {'required': False},
            'profile_photo': {'required': False},
            'ville': {'required': False},
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
        """Ensure email uniqueness when updating with domain validation"""
        if value:
            # Apply strict format validation
            value = validate_email_format_strict(value)
            # Apply domain validation
            value = validate_email_domain(value)

            # Exclude current instance from uniqueness check
            queryset = CustomUser.objects.filter(email__iexact=value)
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError(
                    "A user with this email already exists.")
        return value

    def validate_ville(self, value):
        """Validate ville field against available choices"""
        if value:
            valid_cities = [choice[0] for choice in CustomUser.VILLE_CHOICES]
            if value not in valid_cities:
                raise serializers.ValidationError(
                    f"Invalid city. Allowed cities: {', '.join(valid_cities)}"
                )
        return value

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if password:
            instance.set_password(password)

        instance.save()
        return instance

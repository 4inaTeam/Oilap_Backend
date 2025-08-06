# users/views.py - Complete file with caching

from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.db import transaction
from django.core.cache import cache
import hashlib
import json
import logging

from .models import CustomUser, Client
from .serializers import (
    CustomUserSerializer,
    UserProfileSerializer,
    AdminUserCreateSerializer,
    UserActiveStatusSerializer,
    EmailCINAuthSerializer,
    ClientUpdateSerializer,
    EmployeeAccountantUpdateSerializer
)

logger = logging.getLogger(__name__)

# Simple cache manager (inline to avoid import issues)


class SimpleCacheManager:
    @staticmethod
    def generate_cache_key(prefix, *args, **kwargs):
        key_parts = [prefix]
        key_parts.extend([str(arg) for arg in args])
        if kwargs:
            sorted_kwargs = sorted(kwargs.items())
            kwargs_str = json.dumps(sorted_kwargs, sort_keys=True)
            key_parts.append(hashlib.md5(kwargs_str.encode()).hexdigest()[:8])
        return ':'.join(key_parts)

    @staticmethod
    def get_cache(prefix, *args, **kwargs):
        key = SimpleCacheManager.generate_cache_key(prefix, *args, **kwargs)
        return cache.get(key)

    @staticmethod
    def set_cache(prefix, data, timeout, *args, **kwargs):
        key = SimpleCacheManager.generate_cache_key(prefix, *args, **kwargs)
        return cache.set(key, data, timeout)

    @staticmethod
    def delete_cache(prefix, *args, **kwargs):
        key = SimpleCacheManager.generate_cache_key(prefix, *args, **kwargs)
        return cache.delete(key)


class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role == 'ADMIN'


class IsEmployee(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role == 'EMPLOYEE'


class IsAdminOrEmployee(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role in ['ADMIN', 'EMPLOYEE']


class EmailCINAuthView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = EmailCINAuthSerializer(data=request.data)
        if serializer.is_valid():
            return Response(serializer.validated_data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserCreateView(generics.CreateAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = AdminUserCreateSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)

        # Clear user list cache after creating new user
        if response.status_code == status.HTTP_201_CREATED:
            SimpleCacheManager.delete_cache('users_list', 'all')
            SimpleCacheManager.delete_cache('total_clients')
            logger.info("Cache cleared after user creation")

        return response


class ClientCreateView(generics.CreateAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrEmployee]

    def perform_create(self, serializer):
        user = serializer.save(role='CLIENT')
        Client.objects.create(
            custom_user=user,
            created_by=self.request.user
        )

        # Clear cache after creating client
        SimpleCacheManager.delete_cache('users_list', 'all')
        SimpleCacheManager.delete_cache('total_clients')
        logger.info(f"Cache cleared after client creation: {user.id}")


class UserListView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrEmployee]

    def get(self, request):
        # Try cache first
        cached_users = SimpleCacheManager.get_cache('users_list', 'all')
        if cached_users:
            logger.info("Cache hit for user list")
            return Response(cached_users)

        users = CustomUser.objects.all()
        data = [
            {
                "id": user.id,
                "name": user.username,
                "cin": user.cin,
                "email": user.email,
                "role": user.role,
                "tel": user.tel,
                "profile_photo": user.profile_photo.url if user.profile_photo else None,
                "isActive": user.isActive,
                "ville": user.ville  # Added ville field
            } for user in users
        ]

        # Cache for 10 minutes
        SimpleCacheManager.set_cache('users_list', data, 600, 'all')
        logger.info("Cache set for user list")

        return Response(data)


class UserDeleteView(generics.DestroyAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = UserActiveStatusSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def perform_destroy(self, instance):
        if instance.role == 'CLIENT':
            raise ValidationError("Cannot delete client accounts.")
        if instance.role == 'ADMIN':
            raise ValidationError("Cannot delete admin accounts.")

        user_id = instance.id
        instance.delete()

        # Clear cache after deletion
        SimpleCacheManager.delete_cache('users_list', 'all')
        SimpleCacheManager.delete_cache('user_profile', user_id)
        SimpleCacheManager.delete_cache('total_clients')
        logger.info(f"Cache cleared after user deletion: {user_id}")

        return Response({"message": "User deleted successfully."}, status=status.HTTP_204_NO_CONTENT)


class AdminOnlyView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def get(self, request):
        return Response({"message": "This is an admin-only endpoint."})


class CurrentUserView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user_id = request.user.id

        # Try cache first
        cached_user = SimpleCacheManager.get_cache('user_profile', user_id)
        if cached_user:
            logger.info(f"Cache hit for current user: {user_id}")
            return Response(cached_user)

        serializer = CustomUserSerializer(request.user)
        user_data = serializer.data

        # Cache for 30 minutes
        SimpleCacheManager.set_cache('user_profile', user_data, 1800, user_id)
        logger.info(f"Cache set for current user: {user_id}")

        return Response(user_data)


class SearchClientByCIN(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrEmployee]

    def get(self, request, cin):
        # Try cache first
        cached_client = SimpleCacheManager.get_cache('client_by_cin', cin)
        if cached_client:
            logger.info(f"Cache hit for client search: {cin}")
            return Response(cached_client)

        try:
            client_user = CustomUser.objects.get(cin=cin, role='CLIENT')
            client = Client.objects.get(custom_user=client_user)
            user_serializer = CustomUserSerializer(client.custom_user)

            response_data = {
                "cin": client.custom_user.cin,
                "user": user_serializer.data
            }

            # Cache for 15 minutes
            SimpleCacheManager.set_cache(
                'client_by_cin', response_data, 900, cin)
            logger.info(f"Cache set for client search: {cin}")

            return Response(response_data)
        except (CustomUser.DoesNotExist, Client.DoesNotExist):
            return Response({"message": "Client not found."}, status=status.HTTP_404_NOT_FOUND)


class SearchUserByCIN(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def get(self, request, cin):
        # Try cache first
        cached_user = SimpleCacheManager.get_cache('user_by_cin', cin)
        if cached_user:
            logger.info(f"Cache hit for user search: {cin}")
            return Response(cached_user)

        try:
            user = CustomUser.objects.get(cin=cin)
            user_serializer = CustomUserSerializer(user)

            response_data = {
                "cin": user.cin,
                "user": user_serializer.data
            }

            # Cache for 15 minutes
            SimpleCacheManager.set_cache(
                'user_by_cin', response_data, 900, cin)
            logger.info(f"Cache set for user search: {cin}")

            return Response(response_data)
        except CustomUser.DoesNotExist:
            return Response({"message": "User not found."}, status=status.HTTP_404_NOT_FOUND)


class GetUserById(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrEmployee]

    def get(self, request, user_id):
        # Try cache first
        cached_user = SimpleCacheManager.get_cache('user_by_id', user_id)
        if cached_user:
            logger.info(f"Cache hit for user by ID: {user_id}")
            return Response(cached_user, status=status.HTTP_200_OK)

        try:
            user = CustomUser.objects.get(id=user_id)
            serializer = CustomUserSerializer(user)

            # Cache for 15 minutes
            SimpleCacheManager.set_cache(
                'user_by_id', serializer.data, 900, user_id)
            logger.info(f"Cache set for user by ID: {user_id}")

            return Response(serializer.data, status=status.HTTP_200_OK)
        except CustomUser.DoesNotExist:
            return Response(
                {"message": "User not found."},
                status=status.HTTP_404_NOT_FOUND
            )


class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def perform_update(self, serializer):
        user = serializer.save(role=self.request.user.role)

        # Clear cache after profile update
        user_id = user.id
        SimpleCacheManager.delete_cache('user_profile', user_id)
        SimpleCacheManager.delete_cache('user_by_id', user_id)
        SimpleCacheManager.delete_cache('users_list', 'all')
        if hasattr(user, 'cin'):
            SimpleCacheManager.delete_cache('user_by_cin', user.cin)
            if user.role == 'CLIENT':
                SimpleCacheManager.delete_cache('client_by_cin', user.cin)
        logger.info(f"Cache cleared after profile update: {user_id}")


class UserDeactivateView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def patch(self, request, user_id):
        try:
            user = CustomUser.objects.get(id=user_id)
        except CustomUser.DoesNotExist:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        user.isActive = False
        user.save()

        # Clear cache after deactivation
        SimpleCacheManager.delete_cache('user_profile', user_id)
        SimpleCacheManager.delete_cache('user_by_id', user_id)
        SimpleCacheManager.delete_cache('users_list', 'all')
        if hasattr(user, 'cin'):
            SimpleCacheManager.delete_cache('user_by_cin', user.cin)
            if user.role == 'CLIENT':
                SimpleCacheManager.delete_cache('client_by_cin', user.cin)
        logger.info(f"Cache cleared after user deactivation: {user_id}")

        serializer = UserActiveStatusSerializer(user)
        return Response(serializer.data)


class ClientUpdateView(generics.UpdateAPIView):
    queryset = CustomUser.objects.filter(role='CLIENT')
    serializer_class = ClientUpdateSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrEmployee]
    lookup_field = 'id'

    def perform_update(self, serializer):
        user = serializer.save()

        # Clear cache after client update
        user_id = user.id
        SimpleCacheManager.delete_cache('user_profile', user_id)
        SimpleCacheManager.delete_cache('user_by_id', user_id)
        SimpleCacheManager.delete_cache('users_list', 'all')
        if hasattr(user, 'cin'):
            SimpleCacheManager.delete_cache('user_by_cin', user.cin)
            SimpleCacheManager.delete_cache('client_by_cin', user.cin)
        logger.info(f"Cache cleared after client update: {user_id}")


class EmployeeAccountantUpdateView(generics.UpdateAPIView):
    """
    Update view for Employee and Accountant users.
    Only admins can update employee/accountant information.
    """
    queryset = CustomUser.objects.all()
    serializer_class = EmployeeAccountantUpdateSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]
    lookup_field = 'id'

    def get_queryset(self):
        return CustomUser.objects.filter(role__in=['EMPLOYEE', 'ACCOUNTANT'])

    def get_object(self):
        obj = super().get_object()
        if obj.role not in ['EMPLOYEE', 'ACCOUNTANT']:
            raise ValidationError(
                "Can only update Employee or Accountant users")
        return obj

    def perform_update(self, serializer):
        user = serializer.save()

        # Clear cache after employee/accountant update
        user_id = user.id
        SimpleCacheManager.delete_cache('user_profile', user_id)
        SimpleCacheManager.delete_cache('user_by_id', user_id)
        SimpleCacheManager.delete_cache('users_list', 'all')
        if hasattr(user, 'cin'):
            SimpleCacheManager.delete_cache('user_by_cin', user.cin)
        logger.info(
            f"Cache cleared after employee/accountant update: {user_id}")


class TotalClientsView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrEmployee]

    def get(self, request):
        # Try cache first
        cached_count = SimpleCacheManager.get_cache('total_clients')
        if cached_count is not None:
            logger.info("Cache hit for total clients count")
            return Response({"total_clients": cached_count})

        total_clients = CustomUser.objects.filter(role='CLIENT').count()

        # Cache for 30 minutes
        SimpleCacheManager.set_cache('total_clients', total_clients, 1800)
        logger.info("Cache set for total clients count")

        return Response({"total_clients": total_clients})

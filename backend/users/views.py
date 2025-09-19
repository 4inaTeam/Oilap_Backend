from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.db import transaction
from django.core.cache import cache
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from django.db import models
import hashlib
import json
import logging

from .models import CustomUser, Client, EmailVerificationToken
from .serializers import (
    CustomUserSerializer,
    UserProfileSerializer,
    AdminUserCreateSerializer,
    UserActiveStatusSerializer,
    EmailCINAuthSerializer,
    ClientUpdateSerializer,
    EmployeeAccountantUpdateSerializer
)
from .email_service import EmailVerificationService

logger = logging.getLogger(__name__)


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

        # Send verification email after successful user creation
        if response.status_code == status.HTTP_201_CREATED:
            user = CustomUser.objects.get(id=response.data['id'])
            EmailVerificationService.send_verification_email(user)

            # Clear user list cache after creating new user
            SimpleCacheManager.delete_cache('users_list', 'all')
            SimpleCacheManager.delete_cache('total_clients')
            logger.info(
                f"Cache cleared and verification email sent after user creation: {user.id}")

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

        # Send verification email to new client
        EmailVerificationService.send_verification_email(user)

        # Clear cache after creating client
        SimpleCacheManager.delete_cache('users_list', 'all')
        SimpleCacheManager.delete_cache('total_clients')
        logger.info(
            f"Cache cleared and verification email sent after client creation: {user.id}")


class UserListView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrEmployee]

    def get(self, request):
        # Get query parameters
        role_filter = request.query_params.get('role', None)
        cin_search = request.query_params.get('cin', None)
        name_search = request.query_params.get('name', None)

        # Create cache key based on filters
        cache_params = {}
        if role_filter:
            cache_params['role'] = role_filter
        if cin_search:
            cache_params['cin'] = cin_search
        if name_search:
            cache_params['name'] = name_search

        # Try cache first with filter parameters
        cache_key_suffix = 'all' if not cache_params else str(
            sorted(cache_params.items()))
        cached_users = SimpleCacheManager.get_cache(
            'users_list', cache_key_suffix)
        if cached_users:
            logger.info(
                f"Cache hit for user list with filters: {cache_params}")
            return Response(cached_users)

        # Start with all users
        users_queryset = CustomUser.objects.all()

        # Apply role filter if provided
        if role_filter:
            # Validate role filter
            valid_roles = ['ADMIN', 'EMPLOYEE', 'ACCOUNTANT', 'CLIENT']
            if role_filter.upper() in valid_roles:
                users_queryset = users_queryset.filter(
                    role=role_filter.upper())
            else:
                return Response(
                    {"error": f"Invalid role. Valid roles are: {', '.join(valid_roles)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Apply CIN search if provided
        if cin_search:
            users_queryset = users_queryset.filter(cin__icontains=cin_search)

        # Apply name search if provided
        if name_search:
            users_queryset = users_queryset.filter(
                username__icontains=name_search)

        # Get the filtered users
        users = users_queryset.order_by('-id')  # Order by newest first

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
                "isVerified": user.isVerified,
                "ville": user.ville
            } for user in users
        ]

        # Cache for 10 minutes with filter-specific key
        SimpleCacheManager.set_cache('users_list', data, 600, cache_key_suffix)
        logger.info(f"Cache set for user list with filters: {cache_params}")

        return Response(data)

    def post(self, request):
        """
        Optional: Add a POST method for more complex search queries
        """
        # Get search criteria from request body
        search_criteria = request.data

        role_filter = search_criteria.get('role', None)
        cin_search = search_criteria.get('cin', None)
        name_search = search_criteria.get('name', None)
        is_active = search_criteria.get('isActive', None)
        ville_filter = search_criteria.get('ville', None)
        is_verified = search_criteria.get('isVerified', None)

        # Start with all users
        users_queryset = CustomUser.objects.all()

        # Apply filters
        if role_filter:
            valid_roles = ['ADMIN', 'EMPLOYEE', 'ACCOUNTANT', 'CLIENT']
            if role_filter.upper() in valid_roles:
                users_queryset = users_queryset.filter(
                    role=role_filter.upper())
            else:
                return Response(
                    {"error": f"Invalid role. Valid roles are: {', '.join(valid_roles)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        if cin_search:
            users_queryset = users_queryset.filter(cin__icontains=cin_search)

        if name_search:
            users_queryset = users_queryset.filter(
                username__icontains=name_search)

        if is_active is not None:
            users_queryset = users_queryset.filter(isActive=is_active)

        if ville_filter:
            users_queryset = users_queryset.filter(
                ville__icontains=ville_filter)

        if is_verified is not None:
            users_queryset = users_queryset.filter(isVerified=is_verified)

        # Get the filtered users
        users = users_queryset.order_by('-id')

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
                "isVerified": user.isVerified,
                "ville": user.ville
            } for user in users
        ]

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
    Update view for Employee, Accountant, and Expert Comptable users.
    Only admins can update employee/accountant/expert-comptable information.
    """
    queryset = CustomUser.objects.all()
    serializer_class = EmployeeAccountantUpdateSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]
    lookup_field = 'id'

    def get_queryset(self):
        return CustomUser.objects.filter(role__in=['EMPLOYEE', 'ACCOUNTANT', 'EXPERT_COMPTABLE'])

    def get_object(self):
        obj = super().get_object()
        if obj.role not in ['EMPLOYEE', 'ACCOUNTANT', 'EXPERT_COMPTABLE']:
            raise ValidationError(
                "Can only update Employee, Accountant, or Expert Comptable users")
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


class UserReactivateView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def patch(self, request, user_id):
        try:
            user = CustomUser.objects.get(id=user_id)
        except CustomUser.DoesNotExist:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Check if user is a client
        if user.role != 'CLIENT':
            return Response(
                {'error': 'Only client accounts can be reactivated through this endpoint.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if user is already active
        if user.isActive:
            return Response(
                {'message': 'Client is already active.'},
                status=status.HTTP_200_OK
            )

        # Reactivate the user
        user.isActive = True
        user.save()

        # Clear cache after reactivation
        SimpleCacheManager.delete_cache('user_profile', user_id)
        SimpleCacheManager.delete_cache('user_by_id', user_id)
        SimpleCacheManager.delete_cache('users_list', 'all')
        SimpleCacheManager.delete_cache('total_clients')
        if hasattr(user, 'cin'):
            SimpleCacheManager.delete_cache('user_by_cin', user.cin)
            SimpleCacheManager.delete_cache('client_by_cin', user.cin)
        logger.info(f"Cache cleared after user reactivation: {user_id}")

        serializer = UserActiveStatusSerializer(user)
        return Response({
            'message': 'Client reactivated successfully.',
            'user': serializer.data
        }, status=status.HTTP_200_OK)

class EmailVerificationView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, token):
        """Verify email using token from URL"""
        try:
            # Get the token
            verification_token = get_object_or_404(
                EmailVerificationToken, token=token)

            # Check if token is valid
            if not verification_token.is_valid():
                if verification_token.is_used:
                    return render(request, 'emails/verification_result.html', {
                        'success': False,
                        'message': 'Ce lien de vérification a déjà été utilisé.',
                        'title': 'Lien déjà utilisé'
                    })
                else:
                    return render(request, 'emails/verification_result.html', {
                        'success': False,
                        'message': 'Ce lien de vérification a expiré. Contactez l\'administrateur pour obtenir un nouveau lien.',
                        'title': 'Lien expiré'
                    })

            # Verify the user
            user = verification_token.user
            user.isVerified = True
            user.save()

            # Mark token as used
            verification_token.is_used = True
            verification_token.save()

            # Clear relevant cache
            SimpleCacheManager.delete_cache('user_profile', user.id)
            SimpleCacheManager.delete_cache('user_by_id', user.id)
            if hasattr(user, 'cin'):
                SimpleCacheManager.delete_cache('user_by_cin', user.cin)
                if user.role == 'CLIENT':
                    SimpleCacheManager.delete_cache('client_by_cin', user.cin)

            logger.info(f"Email verified successfully for user: {user.id}")

            return render(request, 'emails/verification_result.html', {
                'success': True,
                'message': f'Félicitations {user.username} ! Votre adresse e-mail a été vérifiée avec succès. Vous pouvez maintenant vous connecter à votre compte.',
                'title': 'Vérification réussie',
                'user': user
            })

        except Exception as e:
            logger.error(f"Email verification error: {e}")
            return render(request, 'emails/verification_result.html', {
                'success': False,
                'message': 'Une erreur s\'est produite lors de la vérification. Veuillez réessayer ou contacter le support.',
                'title': 'Erreur de vérification'
            })


class ResendVerificationEmailView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrEmployee]

    def post(self, request, user_id):
        """Resend verification email to a user"""
        try:
            user = get_object_or_404(CustomUser, id=user_id)

            # Check if user is already verified
            if user.isVerified:
                return Response({
                    'message': 'Cet utilisateur a déjà vérifié son e-mail.'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Check if user is admin/superuser (they don't need verification)
            if user.is_superuser or user.role == 'ADMIN':
                user.isVerified = True
                user.save()
                return Response({
                    'message': f'Utilisateur administrateur automatiquement vérifié: {user.email}'
                }, status=status.HTTP_200_OK)

            # Resend verification email
            success = EmailVerificationService.resend_verification_email(user)

            if success:
                return Response({
                    'message': f'E-mail de vérification renvoyé à {user.email}'
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'message': 'Erreur lors de l\'envoi de l\'e-mail de vérification.'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            logger.error(f"Error resending verification email: {e}")
            return Response({
                'message': 'Une erreur s\'est produite.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserVerificationStatusView(APIView):
    """Get verification status for users"""
    permission_classes = [permissions.IsAuthenticated, IsAdminOrEmployee]

    def get(self, request):
        users = CustomUser.objects.all().order_by('role', 'username')

        verification_data = []
        for user in users:
            verification_data.append({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'cin': user.cin,
                'role': user.role,
                'isActive': user.isActive,
                'isVerified': user.isVerified,
                'needs_verification': user.needs_email_verification() if hasattr(user, 'needs_email_verification') else False,
                'can_login': user.can_login() if hasattr(user, 'can_login') else user.isActive and user.isVerified,
                'verification_tokens_count': EmailVerificationToken.objects.filter(user=user, is_used=False).count()
            })

        return Response({
            'users': verification_data,
            'summary': {
                'total_users': len(verification_data),
                'verified_users': sum(1 for user in verification_data if user['isVerified']),
                'unverified_users': sum(1 for user in verification_data if not user['isVerified']),
                'admin_users': sum(1 for user in verification_data if user['role'] == 'ADMIN'),
                'client_users': sum(1 for user in verification_data if user['role'] == 'CLIENT'),
            }
        })


class BulkVerifyUsersView(APIView):
    """Bulk verify multiple users"""
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def post(self, request):
        user_ids = request.data.get('user_ids', [])

        if not user_ids:
            return Response({
                'error': 'user_ids list is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            users = CustomUser.objects.filter(id__in=user_ids)
            updated_count = 0

            for user in users:
                if not user.isVerified:
                    user.isVerified = True
                    user.save(update_fields=['isVerified'])
                    updated_count += 1

                    # Clear cache
                    SimpleCacheManager.delete_cache('user_profile', user.id)
                    SimpleCacheManager.delete_cache('user_by_id', user.id)
                    if hasattr(user, 'cin'):
                        SimpleCacheManager.delete_cache(
                            'user_by_cin', user.cin)
                        if user.role == 'CLIENT':
                            SimpleCacheManager.delete_cache(
                                'client_by_cin', user.cin)

            # Clear users list cache
            SimpleCacheManager.delete_cache('users_list', 'all')

            return Response({
                'message': f'Successfully verified {updated_count} users',
                'updated_count': updated_count,
                'total_requested': len(user_ids)
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error in bulk verify users: {e}")
            return Response({
                'error': 'An error occurred during bulk verification'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

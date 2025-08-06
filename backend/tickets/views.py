from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from django.utils import timezone
from django.db.models import Q
from .models import Notification
from .serializers import NotificationSerializer
import logging
import re

# Cache imports
from django.core.cache import cache
import hashlib
import json

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


class NotificationPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class NotificationListView(APIView):
    """Get paginated list of notifications for authenticated user"""
    permission_classes = [IsAuthenticated]
    pagination_class = NotificationPagination

    def get(self, request):
        try:
            user = request.user
            user_id = user.id

            # Create cache key for notifications
            page = request.query_params.get('page', 1)
            page_size = request.query_params.get('page_size', 20)

            # Try cache first
            cached_result = SimpleCacheManager.get_cache(
                'notifications_list', user_id, page, page_size)
            if cached_result:
                logger.info(
                    f"Cache hit for notifications: user {user_id}, page {page}")
                return Response(cached_result)

            notifications = Notification.objects.filter(user=user)

            # Apply pagination
            paginator = self.pagination_class()
            paginated_notifications = paginator.paginate_queryset(
                notifications, request)

            serializer = NotificationSerializer(
                paginated_notifications, many=True)

            response_data = paginator.get_paginated_response(
                serializer.data).data

            # Cache for 2 minutes (notifications change frequently)
            SimpleCacheManager.set_cache(
                'notifications_list', response_data, 120, user_id, page, page_size)
            logger.info(
                f"Cache set for notifications: user {user_id}, page {page}")

            return Response(response_data)

        except Exception as e:
            logger.error(f"Error getting notifications: {str(e)}")
            return Response({
                'detail': 'Error loading notifications',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UnreadCountView(APIView):
    """Get count of unread notifications for authenticated user"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            user_id = user.id

            # Try cache first
            cached_count = SimpleCacheManager.get_cache(
                'notifications_unread_count', user_id)
            if cached_count is not None:
                logger.info(f"Cache hit for unread count: user {user_id}")
                return Response({'count': cached_count}, status=status.HTTP_200_OK)

            unread_count = Notification.objects.filter(
                user=user,
                is_read=False
            ).count()

            # Cache for 1 minute (frequently changing)
            SimpleCacheManager.set_cache(
                'notifications_unread_count', unread_count, 60, user_id)
            logger.info(f"Cache set for unread count: user {user_id}")

            return Response({
                'count': unread_count
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error getting unread count: {str(e)}")
            return Response({
                'count': 0,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MarkAsReadView(APIView):
    """Mark a specific notification as read"""
    permission_classes = [IsAuthenticated]

    def post(self, request, notification_id):
        try:
            user = request.user

            # Get notification belonging to the user
            notification = Notification.objects.get(
                id=notification_id,
                user=user
            )

            notification.mark_as_read()

            # Clear cache after marking as read
            user_id = user.id
            SimpleCacheManager.delete_cache(
                'notifications_unread_count', user_id)
            # Clear all pages of notifications cache for this user
            for page in range(1, 10):  # Clear first 10 pages
                for page_size in [20, 50, 100]:
                    SimpleCacheManager.delete_cache(
                        'notifications_list', user_id, page, page_size)

            logger.info(
                f"Cache cleared after marking notification as read: {notification_id}")

            return Response({
                'detail': 'Notification marked as read',
                'notification_id': notification_id
            }, status=status.HTTP_200_OK)

        except Notification.DoesNotExist:
            return Response({
                'detail': 'Notification not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error marking notification as read: {str(e)}")
            return Response({
                'detail': 'Error marking notification as read',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MarkAllAsReadView(APIView):
    """Mark all notifications as read for authenticated user"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            user = request.user

            # Update all unread notifications for this user
            updated_count = Notification.objects.filter(
                user=user,
                is_read=False
            ).update(
                is_read=True,
                read_at=timezone.now()
            )

            # Clear cache after marking all as read
            user_id = user.id
            SimpleCacheManager.delete_cache(
                'notifications_unread_count', user_id)
            # Clear all pages of notifications cache for this user
            for page in range(1, 10):  # Clear first 10 pages
                for page_size in [20, 50, 100]:
                    SimpleCacheManager.delete_cache(
                        'notifications_list', user_id, page, page_size)

            logger.info(
                f"Cache cleared after marking all notifications as read for user: {user_id}")

            return Response({
                'detail': 'All notifications marked as read',
                'updated_count': updated_count
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error marking all notifications as read: {str(e)}")
            return Response({
                'detail': 'Error marking all notifications as read',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TestPushNotificationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        # Get custom title and body from request, with defaults
        title = request.data.get('title', 'Test Notification')
        body = request.data.get('body', 'This is a test push notification')
        data = request.data.get('data', {})

        # Enhanced token validation
        token_info = self.validate_fcm_token(user.fcm_token)

        if not user.can_receive_notifications():
            return Response({
                'detail': 'User cannot receive notifications',
                'has_token': bool(user.fcm_token),
                'token_length': len(user.fcm_token) if user.fcm_token else 0,
                'token_valid': token_info['is_valid'],
                'token_errors': token_info['errors'],
                'notifications_enabled': getattr(user, 'notifications_enabled', True),
                'is_active': getattr(user, 'isActive', True),
                'token_preview': user.fcm_token[:20] + '...' if user.fcm_token and len(user.fcm_token) > 20 else user.fcm_token
            }, status=status.HTTP_400_BAD_REQUEST)

        if not token_info['is_valid']:
            return Response({
                'detail': 'Invalid FCM token',
                'token_errors': token_info['errors'],
                'token_length': len(user.fcm_token) if user.fcm_token else 0,
                'token_preview': user.fcm_token[:20] + '...' if user.fcm_token and len(user.fcm_token) > 20 else user.fcm_token
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            from firebase_admin import messaging

            # Prepare data payload
            notification_data = {
                "type": "test",
                "timestamp": str(timezone.now()),
                **data  # Merge any additional data from request
            }

            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                token=user.fcm_token,
                # FCM data must be strings
                data={k: str(v) for k, v in notification_data.items()},
            )

            response = messaging.send(message)

            # Create notification record
            notification = Notification.objects.create(
                user=user,
                title=title,
                body=body,
                type='test',
                data=notification_data
            )

            # Clear cache after creating notification
            user_id = user.id
            SimpleCacheManager.delete_cache(
                'notifications_unread_count', user_id)
            # Clear notifications list cache
            for page in range(1, 5):  # Clear first 5 pages
                for page_size in [20, 50, 100]:
                    SimpleCacheManager.delete_cache(
                        'notifications_list', user_id, page, page_size)

            logger.info(
                f"Cache cleared after creating test notification for user: {user_id}")

            return Response({
                'detail': 'Test notification sent successfully',
                'message_id': response,
                'user_id': user.id,
                'token_length': len(user.fcm_token)
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error sending test notification: {str(e)}")
            return Response({
                'detail': 'Error sending test notification',
                'error': str(e),
                'token_length': len(user.fcm_token) if user.fcm_token else 0,
                'token_preview': user.fcm_token[:20] + '...' if user.fcm_token and len(user.fcm_token) > 20 else user.fcm_token
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def validate_fcm_token(self, token):
        """Validate FCM token format and structure with more flexible length validation"""
        errors = []

        if not token:
            errors.append("Token is empty or null")
            return {'is_valid': False, 'errors': errors}

        # More flexible token length validation
        if len(token) < 50:
            errors.append(
                f"Token too short ({len(token)} chars), expected at least 50")

        # Check for valid characters (base64url encoding)
        if not re.match(r'^[A-Za-z0-9_-]+$', token):
            errors.append(
                "Token contains invalid characters (only A-Z, a-z, 0-9, _, - allowed)")

        # Check for common formatting issues
        if token.startswith(' ') or token.endswith(' '):
            errors.append("Token has leading/trailing whitespace")

        if '\n' in token or '\r' in token:
            errors.append("Token contains newline characters")

        # Check for obviously invalid tokens
        if len(set(token)) < 10:
            errors.append(
                "Token appears to be invalid (insufficient character diversity)")

        return {
            'is_valid': len(errors) == 0,
            'errors': errors
        }


class UpdateFcmTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = request.data.get('fcm_token')
        if not token:
            return Response({'detail': 'No token provided.'},
                            status=status.HTTP_400_BAD_REQUEST)

        # Clean the token
        token = token.strip()

        # Validate token format
        validation = self.validate_fcm_token(token)
        if not validation['is_valid']:
            return Response({
                'detail': 'Invalid FCM token format',
                'errors': validation['errors'],
                'token_length': len(token),
                'token_preview': token[:20] + '...' if len(token) > 20 else token
            }, status=status.HTTP_400_BAD_REQUEST)

        user = request.user

        try:
            user.update_fcm_token(token)

            # Clear notification-related cache for this user
            user_id = user.id
            SimpleCacheManager.delete_cache(
                'notifications_unread_count', user_id)
            for page in range(1, 5):
                for page_size in [20, 50, 100]:
                    SimpleCacheManager.delete_cache(
                        'notifications_list', user_id, page, page_size)

            logger.info(
                f"FCM token updated and cache cleared for user {user.id}")

            return Response({
                'detail': 'FCM token updated successfully.',
                'user_id': user.id,
                'token_updated': True,
                'token_length': len(token)
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(
                f"Error updating FCM token for user {user.id}: {str(e)}")
            return Response({
                'detail': 'Error updating FCM token.',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def validate_fcm_token(self, token):
        """Validate FCM token format and structure with more flexible length validation"""
        errors = []

        if not token:
            errors.append("Token is empty or null")
            return {'is_valid': False, 'errors': errors}

        if len(token) < 50:
            errors.append(
                f"Token too short ({len(token)} chars), expected at least 50")

        if not re.match(r'^[A-Za-z0-9_-]+$', token):
            errors.append(
                "Token contains invalid characters (only A-Z, a-z, 0-9, _, - allowed)")

        if token.startswith(' ') or token.endswith(' '):
            errors.append("Token has leading/trailing whitespace")

        if '\n' in token or '\r' in token:
            errors.append("Token contains newline characters")

        if len(set(token)) < 10:
            errors.append(
                "Token appears to be invalid (insufficient character diversity)")

        return {
            'is_valid': len(errors) == 0,
            'errors': errors
        }


class DebugFcmTokenView(APIView):
    """Debug view to help troubleshoot FCM token issues"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        token = getattr(user, 'fcm_token', None)

        debug_info = {
            'user_id': user.id,
            'has_token': bool(token),
            'token_length': len(token) if token else 0,
            'token_preview': token[:30] + '...' if token and len(token) > 30 else token,
            'can_receive_notifications': hasattr(user, 'can_receive_notifications') and user.can_receive_notifications(),
            'notifications_enabled': getattr(user, 'notifications_enabled', None),
            'is_active': getattr(user, 'isActive', None),
        }

        if token:
            validation = self.validate_fcm_token(token)
            debug_info.update({
                'token_valid': validation['is_valid'],
                'token_errors': validation['errors'],
                'token_character_count': {
                    'total': len(token),
                    'unique_chars': len(set(token)),
                    'has_spaces': ' ' in token,
                    'has_newlines': '\n' in token or '\r' in token,
                }
            })

        return Response(debug_info, status=status.HTTP_200_OK)

    def validate_fcm_token(self, token):
        """Same validation as other views"""
        errors = []

        if not token:
            errors.append("Token is empty or null")
            return {'is_valid': False, 'errors': errors}

        if len(token) < 50:
            errors.append(
                f"Token too short ({len(token)} chars), expected at least 50")

        if not re.match(r'^[A-Za-z0-9_-]+$', token):
            errors.append(
                "Token contains invalid characters (only A-Z, a-z, 0-9, _, - allowed)")

        if token.startswith(' ') or token.endswith(' '):
            errors.append("Token has leading/trailing whitespace")

        if '\n' in token or '\r' in token:
            errors.append("Token contains newline characters")

        if len(set(token)) < 10:
            errors.append(
                "Token appears to be invalid (insufficient character diversity)")

        return {
            'is_valid': len(errors) == 0,
            'errors': errors
        }

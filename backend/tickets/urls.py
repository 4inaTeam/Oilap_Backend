from django.urls import path
from .views import (
    UpdateFcmTokenView,
    TestPushNotificationView,
    DebugFcmTokenView,
    NotificationListView,
    UnreadCountView,
    MarkAsReadView,
    MarkAllAsReadView
)

app_name = 'tickets'

urlpatterns = [
    # FCM token management
    path('update-fcm-token/', UpdateFcmTokenView.as_view(), name='update_fcm_token'),
    path('test-push/', TestPushNotificationView.as_view(),
         name='test_push_notification'),
    path('debug-fcm-token/', DebugFcmTokenView.as_view(), name='debug_fcm_token'),

    # Notification endpoints to match Flutter NotificationRepository
    path('notifications/', NotificationListView.as_view(),
         name='notifications_list'),
    path('notifications/unread-count/',
         UnreadCountView.as_view(), name='unread_count'),
    path('notifications/<int:notification_id>/mark-read/',
         MarkAsReadView.as_view(), name='mark_as_read'),
    path('notifications/mark-all-read/',
         MarkAllAsReadView.as_view(), name='mark_all_as_read'),
]

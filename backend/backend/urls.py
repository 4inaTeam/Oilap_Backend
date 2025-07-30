from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenRefreshView
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from users.views import EmailCINAuthView
from django.views.static import serve
from django.urls import re_path
import os

schema_view = get_schema_view(
    openapi.Info(
        title="Ollap API",
        default_version='v1',
        description="API pour l'applications OLLAP",
    ),
    public=True,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include([
        path('login/', EmailCINAuthView.as_view(), name='token_obtain_pair'),
        path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    ])),

    path('api/tickets/', include('tickets.urls')),

    path('api/users/', include('users.urls')),
    path('api/products/', include('products.urls')),
    path('api/auth/password/reset/', include('django_rest_passwordreset.urls')),
    path('api/', include('factures.urls')),
    path('api/', include('payments.urls')),
    path('api/', include('webhooks.urls')),
    path('api/', include('bills.urls')),

    path('swagger/', schema_view.with_ui('swagger',
         cache_timeout=0), name='schema-swagger-ui'),
]

# Static files (CSS, JavaScript, Images)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Media files handling - serve both local files and support Cloudinary
if settings.DEBUG:
    # Development: serve media files directly
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)
else:
    # Production: serve local media files that might exist alongside Cloudinary
    # This handles cases where some files might be stored locally
    urlpatterns += [
        re_path(r'^uploads/(?P<path>.*)$', serve, {
            'document_root': settings.MEDIA_ROOT,
        }),
    ]

# Add a debug endpoint to check media file serving
if settings.DEBUG:
    from django.http import JsonResponse
    from django.views.decorators.csrf import csrf_exempt

    def debug_media_info(request):
        """Debug endpoint to check media configuration"""
        media_info = {
            'MEDIA_URL': settings.MEDIA_URL,
            'MEDIA_ROOT': settings.MEDIA_ROOT,
            'DEFAULT_FILE_STORAGE': settings.DEFAULT_FILE_STORAGE,
            'media_root_exists': os.path.exists(settings.MEDIA_ROOT),
            'cloudinary_configured': bool(getattr(settings, 'CLOUDINARY_STORAGE', {}).get('CLOUD_NAME')),
        }

        # List files in media directory
        if os.path.exists(settings.MEDIA_ROOT):
            try:
                media_files = []
                for root, dirs, files in os.walk(settings.MEDIA_ROOT):
                    for file in files:
                        rel_path = os.path.relpath(
                            os.path.join(root, file), settings.MEDIA_ROOT)
                        media_files.append(rel_path)
                # First 10 files
                media_info['local_media_files'] = media_files[:10]
                media_info['total_local_files'] = len(media_files)
            except Exception as e:
                media_info['media_scan_error'] = str(e)

        return JsonResponse(media_info)

    urlpatterns += [
        path('api/debug/media/', debug_media_info, name='debug_media'),
    ]



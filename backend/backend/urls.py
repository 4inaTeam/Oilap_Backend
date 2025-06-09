from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenRefreshView
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from users.views import EmailCINAuthView

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
    path('api/users/', include('users.urls')),
    path('api/products/', include('products.urls')),
    path('api/auth/password/reset/', include('django_rest_passwordreset.urls')),
    path('api/', include('factures.urls')),
    path('api/', include('payments.urls')),
    path('api/', include('webhooks.urls')),
    path('api/invoices/', include('invoices.urls')),
    path('swagger/', schema_view.with_ui('swagger',
         cache_timeout=0), name='schema-swagger-ui'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)

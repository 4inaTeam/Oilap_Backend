from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from .views import SendVerificationEmail, VerifyEmail

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('users.urls')),

    path('api/', include('products.urls')),
]


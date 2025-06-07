from django.urls import path
from . import views

app_name = 'webhooks'

urlpatterns = [
    path('stripe/', views.stripe_webhook, name='stripe_webhook'),
]

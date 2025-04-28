from django.urls import path
from .views import CreatePaymentIntentView, confirm_payment, stripe_webhook

urlpatterns = [
    path('create-payment-intent/', CreatePaymentIntentView.as_view(), name='create-payment-intent'),
    path('confirm-payment/', confirm_payment, name='confirm-payment'),
    path('webhook/', stripe_webhook, name='stripe-webhook'),
]
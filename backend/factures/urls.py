from django.urls import path
from .views import (
    FactureListView,
    FactureDetailView,
    FactureStatusView,
    FacturePDFView,
    QRCodeValidationView,
    QRCodePaymentView,
)

urlpatterns = [
    path('', FactureListView.as_view(), name='facture-list'),
    path('<int:pk>/', FactureDetailView.as_view(), name='facture-detail'),
    path('<int:pk>/status/', FactureStatusView.as_view(), name='facture-status'),
    path('<int:pk>/pdf/', FacturePDFView.as_view(), name='facture-pdf'),
    path('qr/validate/', QRCodeValidationView.as_view(), name='qr-validation'),
    path('qr/pay/', QRCodePaymentView.as_view(), name='qr-payment'),
]
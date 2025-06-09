from django.urls import path
from .views import InvoiceUploadAPIView

urlpatterns = [
    path('classify/', InvoiceUploadAPIView.as_view(), name='invoice-classify'),
]

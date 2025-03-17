from django.urls import path
from .views import ClientInvoiceListView, ComptableInvoiceListView

urlpatterns = [
    path('client/invoices/', ClientInvoiceListView.as_view(), name='client-invoices'),
    path('comptable/invoices/', ComptableInvoiceListView.as_view(), name='comptable-invoices'),
]
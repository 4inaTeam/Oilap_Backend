from django.urls import path
from .views import (
    BillCreateView,
    BillListView,
    BillDetailView,
    BillPDFDownloadView,
)

app_name = 'bills'

urlpatterns = [
    # Bill CRUD operations
    path('bills/', BillCreateView.as_view(), name='bill-create'),
    path('bills/list/', BillListView.as_view(), name='bill-list'),
    path('bills/<int:bill_id>/', BillDetailView.as_view(), name='bill-detail'),

    # PDF download endpoint
    path('bills/<int:bill_id>/download/',
         BillPDFDownloadView.as_view(), name='bill-pdf-download'),

    # Debug endpoint (remove in production)
    # path('bills/debug/', DebugView.as_view(), name='debug'),
]

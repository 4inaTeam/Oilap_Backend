from django.urls import path
from .views import (
    BillCreateView,
    BillListView,
    BillDetailView,
    BillPDFDownloadView,
    BillStatisticsView,
    BillPDFViewView
)

app_name = 'bills'

urlpatterns = [
    path('bills/', BillCreateView.as_view(), name='bill-create'),
    path('bills/list/', BillListView.as_view(), name='bill-list'),
    path('bills/<int:bill_id>/', BillDetailView.as_view(), name='bill-detail'),

    path('bills/statistics/', BillStatisticsView.as_view(), name='bill-statistics'),
    path('bills/<int:bill_id>/download/',
         BillPDFDownloadView.as_view(), name='bill-pdf-download'),
    path('bills/<int:bill_id>/view/',
         BillPDFViewView.as_view(), name='bill-pdf-view'),

    path('bills/<int:bill_id>/download/',
         BillPDFDownloadView.as_view(), name='bill-pdf-download'),
]

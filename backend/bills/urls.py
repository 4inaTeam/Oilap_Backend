from django.urls import path
from .views import (
    BillCreateView,
    BillListView,
    BillDetailView,
    BillPDFDownloadView,
    BillStatisticsView,
    BillPDFViewView,
    BilanListCreateView,
    BilanDetailView,
    ExpertComptableBilanListView,
    ExpertComptableBilanDetailView,
    ExpertComptableBilanCreateView,
    ExpertComptableBilanUpdateView
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
    
    # Bilan endpoints (generic)
    path('bilans/', BilanListCreateView.as_view(), name='bilan-list-create'),
    path('bilans/<int:bilan_id>/', BilanDetailView.as_view(), name='bilan-detail'),
    
    # Expert Comptable specific bilan endpoints
    path('expert-comptable/bilans/', ExpertComptableBilanListView.as_view(), name='expert-bilan-list'),
    path('expert-comptable/bilans/<int:bilan_id>/', ExpertComptableBilanDetailView.as_view(), name='expert-bilan-detail'),
    path('expert-comptable/bilans/create/', ExpertComptableBilanCreateView.as_view(), name='expert-bilan-create'),
    path('expert-comptable/bilans/<int:bilan_id>/update/', ExpertComptableBilanUpdateView.as_view(), name='expert-bilan-update'),
]

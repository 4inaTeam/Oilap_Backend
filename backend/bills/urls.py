from django.urls import path
from .views import BillCreateView, BillListView, BillDetailView

app_name = 'bills'

urlpatterns = [
    path('bills/', BillCreateView.as_view(), name='bill-create'),

    path('bills/list/', BillListView.as_view(), name='bill-list'),

    path('bills/<int:bill_id>/', BillDetailView.as_view(), name='bill-detail'),
]

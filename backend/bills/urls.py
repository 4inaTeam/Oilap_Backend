from django.urls import path
from .views import BillCreateView

urlpatterns = [
    path('bills/', BillCreateView.as_view(), name='bill-create'),
]

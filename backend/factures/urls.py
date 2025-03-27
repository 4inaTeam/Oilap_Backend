from django.urls import path
from .views import (
    FactureListView,
    FactureDetailView,
    FactureStatusView
)

urlpatterns = [
    path('', FactureListView.as_view(), name='facture-list'),
    path('<int:pk>/', FactureDetailView.as_view(), name='facture-detail'),
    path('<int:pk>/status/', FactureStatusView.as_view(), name='facture-status'),
]
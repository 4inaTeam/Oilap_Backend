from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FactureViewSet

router = DefaultRouter()
router.register(r'factures', FactureViewSet, basename='facture')

urlpatterns = [
    path('', include(router.urls)),
]

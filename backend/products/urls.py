# urls.py - Make sure this is exactly how your file looks
from django.urls import path
from .views import (
    ProductCreateView,
    ProductRetrieveView,
    ProductUpdateView,
    ProductListView,
    ClientProductListView,
    SearchProductByStatus,
    AdminClientProductListView,
    CancelProductView,
    ProductReportView,
    SingleProductPDFView,  # Make sure this is imported
    ProductStatsView,
)
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('create/', ProductCreateView.as_view(), name='product-create'),
    path('<int:pk>/', ProductRetrieveView.as_view(), name='product-retrieve'),
    path('<int:pk>/update/', ProductUpdateView.as_view(), name='product-update'),
    path('<int:pk>/cancel/', CancelProductView.as_view(), name='product-cancel'),
    
    path('<int:product_id>/pdf/', SingleProductPDFView.as_view(), name='product-pdf'),
    
    path('', ProductListView.as_view(), name='product-list'),
    path('client/products/', ClientProductListView.as_view(), name='client-product-list'),
    path('search/<str:status>/', SearchProductByStatus.as_view(), name='search-product-by-status'),
    path('admin/client-products/<str:client_cin>/', AdminClientProductListView.as_view(), name='admin-client-products'),
    path('report/', ProductReportView.as_view(), name='product-report'),
    path('stats/', ProductStatsView.as_view(), name='product-stats'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
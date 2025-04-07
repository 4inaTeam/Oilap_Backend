from django.urls import path
from .views import (
    ProductCreateView,
    ProductRetrieveView,  
    ProductUpdateView, 
    ProductDeleteView,
    ProductListView,
    ClientProductListView,  
    SearchProductByStatus,
    CancelProductView,
)
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('create/', ProductCreateView.as_view(), name='product-create'),
    path('<int:pk>/', ProductRetrieveView.as_view(), name='product-retrieve'),
    path('<int:pk>/update/', ProductUpdateView.as_view(), name='product-update'),
    path('<int:pk>/delete/', ProductDeleteView.as_view(), name='product-delete'),
    path('', ProductListView.as_view(), name='product-list'),
    path('client/products/', ClientProductListView.as_view(), name='client-product-list'),
    path('search/<str:status>/', SearchProductByStatus.as_view(), name='search-product-by-status'),
    path('cancel/<int:pk>/', CancelProductView.as_view(), name='cancel-product'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
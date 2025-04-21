from django.urls import path
from .views import (
    ProductCreateView,
    ProductRetrieveView,  
    ProductUpdateView, 
    ProductListView,
    ClientProductListView,  
    SearchProductByStatus,
    CancelProductView,
    AdminClientProductListView
)
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('create/', ProductCreateView.as_view(), name='product-create'),
    path('<int:pk>/', ProductRetrieveView.as_view(), name='product-retrieve'),
    path('<int:pk>/update/', ProductUpdateView.as_view(), name='product-update'),
    path('', ProductListView.as_view(), name='product-list'),
    path('client/products/', ClientProductListView.as_view(), name='client-product-list'),
    path('search/<str:status>/', SearchProductByStatus.as_view(), name='search-product-by-status'),
    path('cancel/<int:pk>/', CancelProductView.as_view(), name='cancel-product'),
    path(
        'admin/client-products/<int:client_id>/',
        AdminClientProductListView.as_view(),
        name='admin-client-products'
    ),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
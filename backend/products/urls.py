from django.urls import path
from .views import (
    ProductCreateView,
    ProductRetrieveView,  
    ProductUpdateView, 
    ProductDeleteView,
    ProductListView,
    ClientProductListView,  
)

urlpatterns = [
    path('products/create/', ProductCreateView.as_view(), name='product-create'),
    path('products/<int:pk>/', ProductRetrieveView.as_view(), name='product-retrieve'),
    path('products/<int:pk>/update/', ProductUpdateView.as_view(), name='product-update'),
    path('products/<int:pk>/delete/', ProductDeleteView.as_view(), name='product-delete'),
    path('products/', ProductListView.as_view(), name='product-list'),
    path('client/products/', ClientProductListView.as_view(), name='client-product-list'),
]
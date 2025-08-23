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
    SingleProductPDFView,
    simple_product_pdf_download,
    ProductStatsView,
    TotalQuantityView,
    OriginPercentageView,

    # NOUVELLES VUES ML
    ml_global_status,
    regenerate_ml_predictions,
    ml_health_check,
)
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [

    path('create/', ProductCreateView.as_view(), name='product-create'),
    path('<int:pk>/', ProductRetrieveView.as_view(), name='product-retrieve'),
    path('<int:pk>/update/', ProductUpdateView.as_view(), name='product-update'),
    path('<int:pk>/cancel/', CancelProductView.as_view(), name='product-cancel'),


    path('<int:product_id>/pdf/', SingleProductPDFView.as_view(), name='product-pdf'),
    path('<int:product_id>/simple-pdf/',
         simple_product_pdf_download, name='simple-product-pdf'),

    path('', ProductListView.as_view(), name='product-list'),
    path('client/products/', ClientProductListView.as_view(),
         name='client-product-list'),
    path('search/<str:status>/', SearchProductByStatus.as_view(),
         name='search-product-by-status'),
    path('admin/client-products/<str:client_cin>/',
         AdminClientProductListView.as_view(), name='admin-client-products'),

    path('report/', ProductReportView.as_view(), name='product-report'),

    path('stats/', ProductStatsView.as_view(), name='product-stats'),
    path('total-quantity/', TotalQuantityView.as_view(),
         name='product-total-quantity'),
    path('origin-percentages/', OriginPercentageView.as_view(),
         name='product-origin-percentages'),


    path('ml-status/', ml_global_status, name='ml-global-status'),
    path('ml-health/', ml_health_check, name='ml-health-check'),
    path('<int:pk>/regenerate-ml/', regenerate_ml_predictions,
         name='regenerate-ml-predictions'),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)



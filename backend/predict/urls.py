from django.urls import path
from .views import (
    PredictEnergyView,
    PredictWaterView,
    PredictEmployeesView,
    PredictAllView,
    PredictQualityView,
    PredictSeasonalView,
    prediction_status,
    clear_prediction_cache,
    generate_prediction_pdf,
)

app_name = 'predict'

urlpatterns = [
    # Main prediction endpoints
    path('energy/', PredictEnergyView.as_view(), name='predict-energy'),
    path('water/', PredictWaterView.as_view(), name='predict-water'),
    path('employees/', PredictEmployeesView.as_view(), name='predict-employees'),
    path('all/', PredictAllView.as_view(), name='predict-all'),
    path('quality/', PredictQualityView.as_view(), name='predict-quality'),
    path('seasonal/', PredictSeasonalView.as_view(), name='predict-seasonal'),

    # PDF report endpoint (legacy - kept for backwards compatibility)
    path('<int:product_id>/pdf-report/', generate_prediction_pdf, name='generate-prediction-pdf'),

    # Service management endpoints
    path('status/', prediction_status, name='prediction-status'),
    path('clear-cache/', clear_prediction_cache, name='clear-prediction-cache'),
]

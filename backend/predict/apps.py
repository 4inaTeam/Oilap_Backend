# predict/apps.py
from django.apps import AppConfig


class PredictConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'predict'
    verbose_name = 'ML Prediction Services'

from django.urls import path
from .views import ClientCreateView

urlpatterns = [
    path('clients/', ClientCreateView.as_view(), name='client-create'),
]
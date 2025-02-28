from django.urls import path
from .views import UserCreateView, ClientCreateView

urlpatterns = [
    path('users/', UserCreateView.as_view(), name='user-create'),
    path('clients/', ClientCreateView.as_view(), name='client-create'),
]
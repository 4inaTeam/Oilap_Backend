# users/urls.py
from django.urls import path
from .views import UserCreateView, ClientCreateView, UserListView, CurrentUserView

urlpatterns = [
    path('users/', UserCreateView.as_view(), name='user-create'),
    path('clients/create/', ClientCreateView.as_view(), name='client-create'),
    path('users/get/', UserListView.as_view(), name='user-liste'),
    path('users/me/', CurrentUserView.as_view(), name='current-user'),
]
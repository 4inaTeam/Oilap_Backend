from django.urls import path
from .views import (
    UserCreateView,
    ClientCreateView,
    UserListView,
    CurrentUserView,
    UserProfileView,
    SearchClientByCIN,
    UserDeactivateView,
    UserDeleteView,
    ClientUpdateView,
    SearchUserByCIN,
    EmployeeAccountantUpdateView,
    GetUserById
)

urlpatterns = [
    path('', UserCreateView.as_view(), name='user-create'),
    path('clients/create/', ClientCreateView.as_view(), name='client-create'),
    path('get/', UserListView.as_view(), name='user-liste'),
    path('me/', CurrentUserView.as_view(), name='current-user'),
    path('me/update/', UserProfileView.as_view(), name='user-profile-update'),
    path('clients/<int:id>/update/',
         ClientUpdateView.as_view(), name='client-update'),
    path('update/<int:id>/', EmployeeAccountantUpdateView.as_view(),
         name='employee-accountant-update'),
    path('delete/<int:pk>/', UserDeleteView.as_view(), name='user-delete'),
    path('search/<str:cin>/', SearchClientByCIN.as_view(),
         name='search-client-by-cin'),
    path('search/users/<str:cin>/',
         SearchUserByCIN.as_view(), name='search-client'),
    path('deactivate/<int:user_id>/',
         UserDeactivateView.as_view(), name='user-deactivate'),
    path('get/<int:user_id>/', GetUserById.as_view(), name='get-user-by-id'),
]

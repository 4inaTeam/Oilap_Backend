from django.urls import path
from .views import UserCreateView, ClientCreateView, UserListView, CurrentUserView, UserProfileView, SearchClientByCIN, UserDeactivateView

urlpatterns = [
    path('', UserCreateView.as_view(), name='user-create'),
    path('clients/create/', ClientCreateView.as_view(), name='client-create'),
    path('get/', UserListView.as_view(), name='user-liste'),
    path('me/', CurrentUserView.as_view(), name='current-user'),
    path('me/update/', UserProfileView.as_view(), name='user-profile-update'),
    path('search/<str:cin>/', SearchClientByCIN.as_view(), name='search-client-by-cin'),
    path('deactivate/<int:user_id>/', UserDeactivateView.as_view(), name='user-deactivate'),
]
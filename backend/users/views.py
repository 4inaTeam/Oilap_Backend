from rest_framework import generics, permissions
from .serializers import CustomUserSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import CustomUser, Client
from .permissions import IsAdmin


class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role == 'ADMIN'

class IsEmployee(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role == 'EMPLOYEE'

class IsAdminOrEmployee(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role in ['ADMIN', 'EMPLOYEE']

class UserCreateView(generics.CreateAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, *args, **kwargs):
        print(f"User role: {request.user.role}")
        print(f"User is authenticated: {request.user.is_authenticated}")
        return super().post(request, *args, **kwargs)


class ClientCreateView(generics.CreateAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrEmployee]

    def perform_create(self, serializer):
        # Create CustomUser with CLIENT role
        custom_user = serializer.save(role='CLIENT')
        
        # Create Client profile
        Client.objects.create(
            custom_user=custom_user,
            created_by=self.request.user
        )
        
class UserListView(APIView):

    def get(self, request):
        users = CustomUser.objects.all()
        data = [{"username": user.username, "role": user.role} for user in users]
        return Response(data)

class AdminOnlyView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        return Response({"message": "This is an admin-only endpoint."})

class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = CustomUserSerializer(request.user)
        return Response(serializer.data)
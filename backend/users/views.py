from rest_framework import generics, permissions
from .serializers import CustomUserSerializer, UserProfileSerializer, AdminUserCreateSerializer, UserActiveStatusSerializer, EmailCINAuthSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import CustomUser, Client
from .permissions import IsAdmin
from rest_framework.exceptions import ValidationError 
from rest_framework import generics 
from django.db import transaction
from rest_framework_simplejwt.views import TokenObtainPairView


class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role == 'ADMIN'

class IsEmployee(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role == 'EMPLOYEE'

class IsAdminOrEmployee(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role in ['ADMIN', 'EMPLOYEE']

class EmailCINAuthView(TokenObtainPairView):
    serializer_class = EmailCINAuthSerializer

class UserCreateView(generics.CreateAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = AdminUserCreateSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, *args, **kwargs):
        print(f"User role: {request.user.role}")
        print(f"User is authenticated: {request.user.is_authenticated}")
        return super().post(request, *args, **kwargs)

class ClientCreateView(generics.CreateAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserSerializer  # Now includes cin/tel validation
    permission_classes = [permissions.IsAuthenticated, IsAdminOrEmployee]

    def perform_create(self, serializer):
        # Assign role=CLIENT and validate CIN via the serializer
        serializer.save(role='CLIENT')

        # Link the created user to a Client profile
        custom_user = serializer.instance
        Client.objects.create(
            custom_user=custom_user,
            created_by=self.request.user
        )

class UserListView(APIView):

    def get(self, request):
        users = CustomUser.objects.all()
        data = [{"username": user.username, "role": user.role, "isActive": user.isActive} for user in users]
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

class SearchClientByCIN(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrEmployee]

    def get(self, request, cin):
        try:
            client = Client.objects.get(cin=cin)
            user_serializer = CustomUserSerializer(client.custom_user)
            return Response({
                "cin": client.cin,
                "user": user_serializer.data
            })
        except Client.DoesNotExist:
            return Response({"message": "Client not found."}, status=404)

class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def perform_update(self, serializer):
        serializer.save(role=self.request.user.role)

class UserDeactivateView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def patch(self, request, user_id):
        try:
            user = CustomUser.objects.get(id=user_id)
        except CustomUser.DoesNotExist:
            return Response({'error': 'User not found.'}, status=404)

        user.isActive = False
        user.save()

        serializer = UserActiveStatusSerializer(user)
        return Response(serializer.data)
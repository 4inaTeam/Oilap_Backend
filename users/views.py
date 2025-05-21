from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.db import transaction

from .models import CustomUser, Client
from .serializers import (
    CustomUserSerializer,
    UserProfileSerializer,
    AdminUserCreateSerializer,
    UserActiveStatusSerializer,
    EmailCINAuthSerializer,
    ClientUpdateSerializer
)

# --- Custom Permissions ---
class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role == 'ADMIN'

class IsEmployee(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role == 'EMPLOYEE'

class IsAdminOrEmployee(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role in ['ADMIN', 'EMPLOYEE']


# --- Auth View ---
class EmailCINAuthView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = EmailCINAuthSerializer(data=request.data)
        if serializer.is_valid():
            return Response(serializer.validated_data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# --- Admin User Creation ---
class UserCreateView(generics.CreateAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = AdminUserCreateSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


# --- Client User Creation ---
class ClientCreateView(generics.CreateAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrEmployee]

    def perform_create(self, serializer):
        serializer.save(role='CLIENT')
        Client.objects.create(
            custom_user=serializer.instance,
            created_by=self.request.user
        )


# --- List All Users ---
class UserListView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def get(self, request):
        users = CustomUser.objects.all()
        data = [
            {
                "cin": user.cin,
                "email": user.email,
                "role": user.role,
                "isActive": user.isActive
            } for user in users
        ]
        return Response(data)


# --- Delete Non-Client/Admin Users ---
class UserDeleteView(generics.DestroyAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = UserActiveStatusSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def perform_destroy(self, instance):
        if instance.role == 'CLIENT':
            raise ValidationError("Cannot delete client accounts.")
        if instance.role == 'ADMIN':
            raise ValidationError("Cannot delete admin accounts.")
        instance.delete()


# --- Admin-Only Test Endpoint ---
class AdminOnlyView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def get(self, request):
        return Response({"message": "This is an admin-only endpoint."})


# --- Get Current User Profile ---
class CurrentUserView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = CustomUserSerializer(request.user)
        return Response(serializer.data)


# --- Search Client by CIN ---
class SearchClientByCIN(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrEmployee]

    def get(self, request, cin):
        try:
            client_user = CustomUser.objects.get(cin=cin, role='CLIENT')
            client = Client.objects.get(custom_user=client_user)
            user_serializer = CustomUserSerializer(client.custom_user)
            return Response({
                "cin": client.custom_user.cin,
                "user": user_serializer.data
            })
        except (CustomUser.DoesNotExist, Client.DoesNotExist):
            return Response({"message": "Client not found."}, status=status.HTTP_404_NOT_FOUND)


# --- Update Current User Profile ---
class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def perform_update(self, serializer):
        serializer.save(role=self.request.user.role)


# --- Deactivate User by ID ---
class UserDeactivateView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def patch(self, request, user_id):
        try:
            user = CustomUser.objects.get(id=user_id)
        except CustomUser.DoesNotExist:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        user.isActive = False
        user.save()

        serializer = UserActiveStatusSerializer(user)
        return Response(serializer.data)


# --- Update Client Info ---
class ClientUpdateView(generics.UpdateAPIView):
    queryset = CustomUser.objects.filter(role='CLIENT')
    serializer_class = ClientUpdateSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrEmployee]
    lookup_field = 'id'

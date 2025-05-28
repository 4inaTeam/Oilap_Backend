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
    ClientUpdateSerializer,
    EmployeeAccountantUpdateSerializer
)


class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role == 'ADMIN'


class IsEmployee(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role == 'EMPLOYEE'


class IsAdminOrEmployee(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role in ['ADMIN', 'EMPLOYEE']


class EmailCINAuthView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = EmailCINAuthSerializer(data=request.data)
        if serializer.is_valid():
            return Response(serializer.validated_data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserCreateView(generics.CreateAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = AdminUserCreateSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


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


class UserListView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def get(self, request):
        users = CustomUser.objects.all()
        data = [
            {
                "id": user.id,
                "name": user.username,
                "cin": user.cin,
                "email": user.email,
                "role": user.role,
                "tel": user.tel,
                "profile_photo": user.profile_photo.url if user.profile_photo else None,
                "isActive": user.isActive
            } for user in users
        ]
        return Response(data)


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
        return Response({"message": "User deleted successfully."}, status=status.HTTP_204_NO_CONTENT)


class AdminOnlyView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def get(self, request):
        return Response({"message": "This is an admin-only endpoint."})


class CurrentUserView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = CustomUserSerializer(request.user)
        return Response(serializer.data)


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


class SearchUserByCIN(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def get(self, request, cin):
        try:
            user = CustomUser.objects.get(cin=cin)
            user_serializer = CustomUserSerializer(user)
            return Response({
                "cin": user.cin,
                "user": user_serializer.data
            })
        except CustomUser.DoesNotExist:
            return Response({"message": "User not found."}, status=status.HTTP_404_NOT_FOUND)


class GetUserById(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def get(self, request, user_id): 
        try:
            user = CustomUser.objects.get(id=user_id)
            serializer = CustomUserSerializer(user)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except CustomUser.DoesNotExist:
            return Response(
                {"message": "User not found."},
                status=status.HTTP_404_NOT_FOUND
            )


class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def perform_update(self, serializer):
        serializer.save(role=self.request.user.role)


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


class ClientUpdateView(generics.UpdateAPIView):
    queryset = CustomUser.objects.filter(role='CLIENT')
    serializer_class = ClientUpdateSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrEmployee]
    lookup_field = 'id'


class EmployeeAccountantUpdateView(generics.UpdateAPIView):
    """
    Update view for Employee and Accountant users.
    Only admins can update employee/accountant information.
    """
    serializer_class = EmployeeAccountantUpdateSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]
    lookup_field = 'id'

    def get_queryset(self):
        """Only allow updating EMPLOYEE and ACCOUNTANT users"""
        return CustomUser.objects.filter(role__in=['EMPLOYEE', 'ACCOUNTANT'])

    def patch(self, request, *args, **kwargs):
        """Handle partial updates"""
        return super().patch(request, *args, **kwargs)

    def put(self, request, *args, **kwargs):
        """Handle full updates"""
        return super().put(request, *args, **kwargs)

    def perform_update(self, serializer):
        """Additional logic before saving the update"""
        user = serializer.save()

        # You can add additional logic here if needed
        # For example, logging the update or sending notifications
        return user

from rest_framework.permissions import BasePermission

class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        print(f"User role: {request.user.role}")  # Debugging
        return request.user.role == 'ADMIN'

class IsEmployee(BasePermission):
    def has_permission(self, request, view):
        return request.user.role == 'EMPLOYEE'
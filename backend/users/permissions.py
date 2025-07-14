# backend/users/permissions.py
from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            hasattr(request.user, 'role') and
            request.user.role == 'ADMIN'
        )


class IsEmployee(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            hasattr(request.user, 'role') and
            request.user.role == 'EMPLOYEE'
        )


class IsClient(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            hasattr(request.user, 'role') and
            request.user.role == 'CLIENT'
        )


class IsAccountant(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            hasattr(request.user, 'role') and
            request.user.role == 'ACCOUNTANT'
        )


class IsAdminOrAccountant(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            hasattr(request.user, 'role') and
            request.user.role in ['ADMIN', 'ACCOUNTANT']
        )


class IsOwnerOrAdminOrAccountant(BasePermission):
    """
    Custom permission to allow:
    - Bill owners to access their own bills
    - Admins and Accountants to access any bill
    """

    def has_permission(self, request, view):
        # User must be authenticated
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Owner can always access their bill
        if obj.user == request.user:
            return True

        # Admin and Accountant can access any bill
        if hasattr(request.user, 'role') and request.user.role in ['ADMIN', 'ACCOUNTANT']:
            return True

        return False

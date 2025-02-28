from django.test import TestCase, RequestFactory
from django.urls import reverse
from rest_framework.test import APIClient
from .models import CustomUser
from .permissions import IsAdmin, IsEmployee


class CustomUserModelTest(TestCase):
    def test_create_user(self):
        user = CustomUser.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='testpass123',
            role='CLIENT'
        )

        # Check if the user was created correctly
        self.assertEqual(user.username, 'testuser')
        self.assertEqual(user.email, 'testuser@example.com')
        self.assertEqual(user.role, 'CLIENT')
        self.assertTrue(user.check_password('testpass123'))
        self.assertFalse(user.is_superuser)  # Ensure it's not a superuser

    def test_create_superuser(self):
        admin_user = CustomUser.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            role='ADMIN'
        )

        self.assertEqual(admin_user.username, 'admin')
        self.assertEqual(admin_user.role, 'ADMIN')
        self.assertTrue(admin_user.is_superuser)


class UserCreateViewTest(TestCase):
    def setUp(self):
        self.admin_user = CustomUser.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            role='ADMIN'
        )
        self.client = APIClient()

    def test_create_user_as_admin(self):
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.post(
            reverse('user-create'),
            {
                'username': 'newuser',
                'email': 'newuser@example.com',
                'password': 'newpass123',
                'role': 'EMPLOYEE'
            },
            format='json'
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(CustomUser.objects.count(), 2)  # Admin + new user

    def test_create_user_as_non_admin(self):

        non_admin_user = CustomUser.objects.create_user(
            username='employee',
            email='employee@example.com',
            password='employeepass123',
            role='EMPLOYEE'
        )
        self.client.force_authenticate(user=non_admin_user)

        response = self.client.post(
            reverse('user-create'),
            {
                'username': 'newuser',
                'email': 'newuser@example.com',
                'password': 'newpass123',
                'role': 'EMPLOYEE'
            },
            format='json'
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(CustomUser.objects.count(), 2)  # Admin + employee (no new user)


class PermissionTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.admin_user = CustomUser.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            role='ADMIN'
        )
        self.employee_user = CustomUser.objects.create_user(
            username='employee',
            email='employee@example.com',
            password='employeepass123',
            role='EMPLOYEE'
        )
        self.client_user = CustomUser.objects.create_user(
            username='client',
            email='client@example.com',
            password='clientpass123',
            role='CLIENT'
        )

    def test_is_admin_permission(self):
        request = self.factory.get('/fake-url')
        request.user = self.admin_user
        permission = IsAdmin()

        self.assertTrue(permission.has_permission(request, None))

        request.user = self.employee_user
        self.assertFalse(permission.has_permission(request, None))

    def test_is_employee_permission(self):
        request = self.factory.get('/fake-url')
        request.user = self.employee_user
        permission = IsEmployee()

        self.assertTrue(permission.has_permission(request, None))

        request.user = self.client_user
        self.assertFalse(permission.has_permission(request, None))
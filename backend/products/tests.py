from django.urls import reverse
from rest_framework.test import APITestCase
from .models import Product
from users.models import CustomUser
from clients.models import Client

class ProductRetrieveUpdateDeleteTest(APITestCase):
    def setUp(self):
        # Create an employee user
        self.employee = CustomUser.objects.create_user(
            username='employee',
            email='employee@example.com',
            password='employeepass123',
            role='EMPLOYEE'
        )
        self.client.force_authenticate(user=self.employee)

        # Create a client
        self.client_obj = Client.objects.create(
            name="John Doe",
            email="john@example.com",
            phone="1234567890",
            created_by=self.employee
        )

        # Create a product
        self.product = Product.objects.create(
            name="Olive Oil",
            quality="Extra virgin",
            price=25.99,
            origine="Italy",
            client=self.client_obj,
            created_by=self.employee
        )

    def test_retrieve_product(self):
        response = self.client.get(reverse('product-retrieve', args=[self.product.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['name'], "Olive Oil")

    def test_delete_product(self):
        response = self.client.delete(reverse('product-delete', args=[self.product.id]))
        self.assertEqual(response.status_code, 204)
        self.assertEqual(Product.objects.count(), 0)

class ProductUpdateViewTest(APITestCase):
    def setUp(self):
        # Create an employee user
        self.employee = CustomUser.objects.create_user(
            username='employee',
            email='employee@example.com',
            password='employeepass123',
            role='EMPLOYEE'
        )

        # Create a client user
        self.client_user = CustomUser.objects.create_user(
            username='client',
            email='client@example.com',
            password='clientpass123',
            role='CLIENT'
        )

        # Create a client
        self.client_obj = Client.objects.create(
            name="John Doe",
            email="john@example.com",
            phone="1234567890",
            created_by=self.employee
        )

        # Create a product
        self.product = Product.objects.create(
            name="Olive Oil",
            quality="Extra virgin",
            origine="Tunisia",
            price=25.99,
            client=self.client_obj,
            created_by=self.employee,
            status='pending'
        )

    def test_employee_can_update_status(self):
        self.client.force_authenticate(user=self.employee)
        response = self.client.put(
            reverse('product-update', args=[self.product.id]),
            {"status": "doing"},
            format='json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], "doing")

    def test_employee_cannot_update_info_when_status_is_doing(self):
        # Set status to "doing"
        self.product.status = 'doing'
        self.product.save()

        self.client.force_authenticate(user=self.employee)
        response = self.client.put(
            reverse('product-update', args=[self.product.id]),
            {"name": "Premium Olive Oil"},
            format='json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['detail'], "Cannot update product information when status is 'doing'. Only status can be updated to 'done'.")

    def test_non_employee_cannot_update_status(self):
        self.client.force_authenticate(user=self.client_user)
        response = self.client.put(
            reverse('product-update', args=[self.product.id]),
            {"status": "done"},
            format='json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['detail'], "Only employees can update the status of a product.")

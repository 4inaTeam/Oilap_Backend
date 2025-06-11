import logging
from rest_framework import generics, permissions
from .models import Product
from .serializers import ProductSerializer
from users.permissions import IsEmployee, IsAdmin, IsClient
from users.models import CustomUser
from rest_framework.exceptions import ValidationError
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import generics
from rest_framework.exceptions import NotFound
from django.utils import timezone

logger = logging.getLogger(__name__)


class IsAdminOrEmployee(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role in ['ADMIN', 'EMPLOYEE']


class ProductCreateView(generics.CreateAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrEmployee]


class ProductRetrieveView(generics.RetrieveAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrEmployee]


class ProductUpdateView(generics.UpdateAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrEmployee]

    def perform_update(self, serializer):
        instance = self.get_object()
        old_status = instance.status

        logger.info(
            f"Updating product {instance.id} - Current status: {old_status}")

        if instance.status == 'done':
            raise ValidationError(
                "Cannot update a product with 'done' status.")

        new_status = serializer.validated_data.get('status', instance.status)
        logger.info(f"New status for product {instance.id}: {new_status}")

        # Set end_time when status changes to done
        if new_status == 'done':
            serializer.validated_data['end_time'] = timezone.now()
            logger.info(f"Setting end_time to now for product {instance.id}")

        # Check permissions for status updates
        if 'status' in serializer.validated_data:
            if self.request.user.role not in ['EMPLOYEE', 'ADMIN']:
                raise ValidationError(
                    "Only employees or admins can update the status of a product.")

        # Handle 'doing' status restrictions
        if instance.status == 'doing':
            if new_status != 'done':
                raise ValidationError(
                    "Products in 'doing' status can only be marked as 'done'.")

            # When transitioning from 'doing' to 'done', only allow status change
            validated_data_copy = serializer.validated_data.copy()
            for field in list(validated_data_copy.keys()):
                if field not in ['status', 'end_time']:  # Allow end_time to be updated
                    del validated_data_copy[field]

            serializer.validated_data.clear()
            serializer.validated_data.update(validated_data_copy)

        # Save the instance
        saved_instance = serializer.save()
        logger.info(
            f"Product {saved_instance.id} updated successfully - Status: {saved_instance.status}, Payment: {saved_instance.payement}")

        return saved_instance


class CancelProductView(generics.UpdateAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrEmployee]

    def perform_update(self, serializer):
        instance = self.get_object()

        if instance.status != 'pending':
            raise ValidationError(
                "Can only cancel products in 'pending' status.")

        serializer.validated_data['status'] = 'canceled'
        serializer.save()


class ProductListView(generics.ListAPIView):
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated,
                          IsEmployee | IsAdmin | IsClient]

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'role') and user.role in ['ADMIN', 'EMPLOYEE']:
            return Product.objects.all()
        return Product.objects.filter(client=user)


class ClientProductListView(generics.ListAPIView):
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated, IsClient]

    def get_queryset(self):
        return Product.objects.filter(client=self.request.user)\
            .select_related('client', 'created_by')\
            .order_by('-created_at')


class SearchProductByStatus(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrEmployee]

    def get(self, request, status):
        try:
            products = Product.objects.filter(status=status)
            if not products.exists():
                return Response({"message": "No products found with this status."}, status=404)

            serializer = ProductSerializer(products, many=True)
            return Response(serializer.data)
        except Product.DoesNotExist:
            return Response({"message": "Product not found."}, status=404)


class AdminClientProductListView(generics.ListAPIView):
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrEmployee]

    def get_queryset(self):
        client_id = self.kwargs['client_id']
        try:
            client = CustomUser.objects.get(id=client_id, role='CLIENT')
        except CustomUser.DoesNotExist:
            raise NotFound(detail="Client not found or invalid client role")

        return Product.objects.filter(client=client)

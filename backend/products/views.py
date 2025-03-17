from rest_framework import generics, permissions
from .models import Product
from .serializers import  ProductSerializer
from users.permissions import IsEmployee, IsAdmin, IsClient
from rest_framework.exceptions import ValidationError

class ProductCreateView(generics.CreateAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated, IsEmployee]


class ProductRetrieveView(generics.RetrieveAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated, IsEmployee]

class ProductUpdateView(generics.UpdateAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated, IsEmployee]

    def perform_update(self, serializer):
        instance = self.get_object()
        new_status = serializer.validated_data.get('status', instance.status)

        if 'status' in serializer.validated_data:
            if not self.request.user.role == 'EMPLOYEE':
                raise ValidationError("Only employees can update the status of a product.")

        if instance.status == 'doing':
            if new_status != 'done':
                raise ValidationError("Cannot update product information when status is 'doing'. Only status can be updated to 'done'.")

        # Create a copy and modify it
            validated_data_copy = serializer.validated_data.copy()
            for field in list(validated_data_copy.keys()):
                if field != 'status':
                    del validated_data_copy[field]

            serializer.validated_data.clear() 
            serializer.validated_data.update(validated_data_copy)

        serializer.save()


class ProductDeleteView(generics.DestroyAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated, IsEmployee]


class ProductListView(generics.ListAPIView):
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated, IsEmployee | IsAdmin]  # Fix typo

    def get_queryset(self):
        return Product.objects.all()


class ClientProductListView(generics.ListAPIView):
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated, IsClient]

    def get_queryset(self):
        return Product.objects.filter(client__custom_user=self.request.user)


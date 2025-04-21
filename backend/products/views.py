from rest_framework import generics, permissions
from .models import Product
from .serializers import  ProductSerializer
from users.permissions import IsEmployee, IsAdmin, IsClient
from users.models import CustomUser
from rest_framework.exceptions import ValidationError
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import generics
from rest_framework.exceptions import NotFound


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
        new_status = serializer.validated_data.get('status', instance.status)

        if 'status' in serializer.validated_data:
            if self.request.user.role not in ['EMPLOYEE', 'ADMIN']:
                raise ValidationError("Only employees or admins can update the status of a product.")

        if instance.status == 'doing':
            if new_status != 'done':
                raise ValidationError("Cannot update product information when status is 'doing'. Only status can be updated to 'done'.")

            validated_data_copy = serializer.validated_data.copy()
            for field in list(validated_data_copy.keys()):
                if field != 'status':
                    del validated_data_copy[field]

            serializer.validated_data.clear() 
            serializer.validated_data.update(validated_data_copy)

        serializer.save()



class ProductListView(generics.ListAPIView):
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated, IsEmployee | IsAdmin]

    def get_queryset(self):
        return Product.objects.all()


class ClientProductListView(generics.ListAPIView):
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated, IsClient]

    def get_queryset(self):
        return Product.objects.filter(client=self.request.user)

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

class CancelProductView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrEmployee] 

    def post(self, request, product_id):
        try:
            product = Product.objects.get(id=product_id)
            if product.status == 'done':
                return Response({"message": "Cannot cancel a product with status 'done'."}, status=400)

            product.status = 'canceled'
            product.save()
            serializer = ProductSerializer(product)
            return Response(serializer.data, status=200)
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
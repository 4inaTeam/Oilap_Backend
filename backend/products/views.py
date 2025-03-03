# products/views.py
from rest_framework import generics, permissions
from .models import Product
from .serializers import ProductWithClientSerializer
from users.permissions import IsEmployee  # Import IsEmployee from users.permissions

class ProductCreateView(generics.CreateAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductWithClientSerializer
    permission_classes = [permissions.IsAuthenticated, IsEmployee]  # Use IsEmployee

    def perform_create(self, serializer):
        # Pass the request user (employee) to the serializer
        serializer.save(created_by=self.request.user)
from rest_framework import generics, permissions
from .models import Client
from .serializers import ClientSerializer

class ClientCreateView(generics.CreateAPIView):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    permission_classes = [permissions.IsAuthenticated, IsEmployee]
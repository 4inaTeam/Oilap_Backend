from rest_framework import generics, permissions
from .models import Invoice
from .serializers import InvoiceSerializer
from users.permissions import IsClient, IsAccountant

class ClientInvoiceListView(generics.ListAPIView):
    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated, IsClient]

    def get_queryset(self):
        return Invoice.objects.filter(client=self.request.user.client)

class ComptableInvoiceListView(generics.ListAPIView):
    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated, IsAccountant]

    def get_queryset(self):
        return Invoice.objects.filter(comptable=self.request.user)
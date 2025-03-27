from rest_framework import generics, permissions
from .models import Facture
from .serializers import FactureSerializer, FactureStatusSerializer
from users.permissions import IsAdmin, IsAccountant, IsEmployee, IsClient

class FactureListView(generics.ListAPIView):
    serializer_class = FactureSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'ADMIN':
            return Facture.objects.all()
        if user.role == 'ACCOUNTANT':
            return Facture.objects.filter(accountant=user)
        if user.role == 'EMPLOYEE':
            return Facture.objects.filter(employee=user)
        if user.role == 'CLIENT':
            return Facture.objects.filter(client__custom_user=user)
        return Facture.objects.none()

class FactureDetailView(generics.RetrieveAPIView):
    queryset = Facture.objects.all()
    serializer_class = FactureSerializer
    permission_classes = [permissions.IsAuthenticated]

class FactureStatusView(generics.UpdateAPIView):
    queryset = Facture.objects.all()
    serializer_class = FactureStatusSerializer
    permission_classes = [permissions.IsAuthenticated, IsAccountant]

    def perform_update(self, serializer):
        instance = self.get_object()
        new_status = serializer.validated_data.get('status')
        
        if new_status == 'paid':
            serializer.validated_data['payment_date'] = timezone.now()
        
        serializer.save()
        
        # TODO: Add status change notification
        # send_status_notification(instance, new_status)
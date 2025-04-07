import io
import stripe
from rest_framework import generics, permissions
from .models import Facture
from .serializers import FactureSerializer, FactureStatusSerializer, QRCodeValidationSerializer, QRCodePaymentSerializer
from users.permissions import IsAdmin, IsAccountant, IsEmployee, IsClient
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import NotFound, PermissionDenied
from .models import Facture
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from decimal import Decimal
from rest_framework.response import Response
from rest_framework import status

class FacturePDFView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, format=None):
        try:
            facture = Facture.objects.get(pk=pk)
        except Facture.DoesNotExist:
            raise NotFound("Facture not found.")

        user = request.user
        if user.role not in ['ADMIN', 'ACCOUNTANT']:
            if user.role == 'EMPLOYEE' and facture.employee != user:
                raise PermissionDenied("You do not have permission to generate a PDF for this Facture.")
            elif user.role == 'CLIENT' and facture.client.custom_user != user:
                raise PermissionDenied("You do not have permission to generate a PDF for this Facture.")
            elif user.role not in ['EMPLOYEE', 'CLIENT']:
                raise PermissionDenied("You do not have permission to generate a PDF for this Facture.")

        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter
        y = height - 50 
        line_height = 20

        p.setFont("Helvetica-Bold", 14)
        p.drawString(50, y, "Facture Details")
        p.setFont("Helvetica", 12)
        y -= line_height * 2

        p.drawString(50, y, f"Facture ID: {facture.id}")
        y -= line_height

        product_info = facture.product.name if facture.product else "N/A"
        p.drawString(50, y, f"Product: {product_info}")
        y -= line_height

        client_info = facture.client.username if hasattr(facture.client, 'username') else f"ID {facture.client.cin}"
        p.drawString(50, y, f"Client: {client_info}")
        y -= line_height

        employee_info = facture.employee.username if facture.employee else "N/A"
        p.drawString(50, y, f"Employee: {employee_info}")
        y -= line_height

        accountant_info = facture.accountant.username if facture.accountant else "N/A"
        p.drawString(50, y, f"Accountant: {accountant_info}")
        y -= line_height

        p.drawString(50, y, f"Base Amount: {facture.base_amount}")
        y -= line_height
        p.drawString(50, y, f"Tax Amount: {facture.tax_amount}")
        y -= line_height
        p.drawString(50, y, f"Total Amount: {facture.total_amount}")
        y -= line_height

        p.drawString(50, y, f"Issue Date: {facture.issue_date}")
        y -= line_height
        p.drawString(50, y, f"Due Date: {facture.due_date}")
        y -= line_height
        p.drawString(50, y, f"Status: {facture.status}")
        y -= line_height

        payment_date = facture.payment_date.strftime("%Y-%m-%d %H:%M") if facture.payment_date else "N/A"
        p.drawString(50, y, f"Payment Date: {payment_date}")
        y -= line_height
        p.drawString(50, y, f"Created At: {facture.created_at}")
        y -= line_height


        p.showPage()
        p.save()

        buffer.seek(0)
        return HttpResponse(buffer, content_type='application/pdf')

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
        
        if new_status == 'paid':
            send_fcm_notification(
                user=instance.client.custom_user,
                title="Facture Payée",
                body=f"La facture #{instance.id} a été marquée comme payée",
                data={
                    'type': 'facture_paid',
                    'facture_id': str(instance.id)
                }
            )

class QRCodeValidationView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAccountant]
    
    def post(self, request):
        serializer = QRCodeValidationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        qr_data = serializer.validated_data['qr_data']
        
        try:
            facture = Facture.objects.get(
                id=qr_data['facture_id'],
                payment_uuid=qr_data['uuid'],
                total_amount=Decimal(qr_data['amount']),
                qr_verified=False
            )
            return Response({
                'facture_id': facture.id,
                'client': facture.client.custom_user.get_full_name(),
                'amount': facture.total_amount,
                'status': 'valid'
            }, status=status.HTTP_200_OK)
            
        except Facture.DoesNotExist:
            return Response({'error': 'Facture non valide'}, status=400)

class QRCodePaymentView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAccountant]
    
    def post(self, request):
        serializer = QRCodePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            facture = Facture.objects.get(
                id=serializer.validated_data['facture_id'],
                payment_uuid=serializer.validated_data['payment_uuid'],
                qr_verified=False
            )
            
            payment_intent = stripe.PaymentIntent.create(
                amount=int(facture.total_amount * 100),
                currency='eur',
                payment_method_types=['card'],
                metadata={
                    'facture_id': facture.id,
                    'payment_type': 'qr_code'
                }
            )
            
            facture.qr_verified = True
            facture.save()
            
            return Response({
                'client_secret': payment_intent.client_secret,
                'payment_id': payment_intent.id
            }, status=status.HTTP_200_OK)
            
        except Facture.DoesNotExist:
            return Response({'error': 'Facture non valide'}, status=400)
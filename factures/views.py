import os
import io
import stripe
from rest_framework import generics, permissions
from .models import Facture
from payments.models import Payment
from .serializers import FactureSerializer, FactureStatusSerializer, QRCodeValidationSerializer, QRCodePaymentSerializer, FactureCreateSerializer
from users.permissions import IsAdminOrAccountant
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
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ValidationError
from .models import Facture
from ml_model.model_loader import InvoiceClassifier
from datetime import datetime
import logging
from PIL import Image, UnidentifiedImageError
from django.conf import settings
import threading


class FacturePDFView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, format=None):
        try:
            facture = Facture.objects.get(pk=pk)
        except Facture.DoesNotExist:
            raise NotFound("Facture not found.")

        user = request.user
        if facture.type == 'CLIENT':
            if not (user.role in ['ADMIN', 'ACCOUNTANT'] or 
                    (user.role == 'CLIENT' and facture.client == user)):
                raise PermissionDenied()
        else:
            if user.role not in ['ADMIN', 'ACCOUNTANT']:
                raise PermissionDenied()

        if facture.type != 'CLIENT':
            if not facture.pdf_file:
                return Response(
                    {"error": "PDF not available."},
                    status=status.HTTP_404_NOT_FOUND
                )
            response = HttpResponse(facture.pdf_file.read(), content_type='application/pdf')
            response['Content-Disposition'] = f'filename="facture_{facture.id}.pdf"'
            return response
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter
        y = height - 50 
        line_height = 20

        p.setFont("Helvetica-Bold", 14)
        title = f"{facture.get_type_display()} Details"
        p.drawString(50, y, title)
        p.setFont("Helvetica", 12)
        y -= line_height * 2

        p.drawString(50, y, f"Facture ID: {facture.id}")
        y -= line_height

        # Only show product/client for CLIENT type
        if facture.type == 'CLIENT':
            product_info = facture.product.id if facture.product else "N/A"
            p.drawString(50, y, f"Product: {product_info}")
            y -= line_height

            client_info = facture.client.username if facture.client else "N/A"
            p.drawString(50, y, f"Client: {client_info}")
            y -= line_height

        # Common fields for all facture types
        p.drawString(50, y, f"Type: {facture.get_type_display()}")
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

        # Payment info
        payment_date = facture.payment_date.strftime("%Y-%m-%d %H:%M") if facture.payment_date else "N/A"
        p.drawString(50, y, f"Payment Date: {payment_date}")
        y -= line_height
        p.drawString(50, y, f"Created At: {facture.created_at}")
        y -= line_height

        # QR code handling
        if facture.qr_code:
            try:
                qr_code_path = facture.qr_code.path
                if os.path.exists(qr_code_path):
                    p.drawImage(qr_code_path, 50, 100, width=150, height=150)
                else:
                    p.drawString(50, 100, "QR Code not found.")
            except Exception as e:
                p.drawString(50, 100, f"Error loading QR code: {str(e)}")

        p.showPage()
        p.save()

        buffer.seek(0)
        return HttpResponse(buffer, content_type='application/pdf')

def get_queryset(self):
    user = self.request.user
    if user.role == 'ADMIN':
        return Facture.objects.all()
    if user.role == 'ACCOUNTANT':
        return Facture.objects.filter(accountant=user)
    if user.role == 'CLIENT':
        return Facture.objects.filter(client=user, type='CLIENT')
    return Facture.objects.none()

class FactureListView(generics.ListAPIView):
    serializer_class = FactureSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'ADMIN':
            return Facture.objects.all()
        if user.role == 'ACCOUNTANT':
            return Facture.objects.filter(accountant=user)
        if user.role == 'CLIENT':
            return Facture.objects.filter(client=user)
        return Facture.objects.none()


class FactureDetailView(generics.RetrieveAPIView):
    queryset = Facture.objects.all()
    serializer_class = FactureSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrAccountant]

class FactureStatusView(generics.UpdateAPIView):
    queryset = Facture.objects.all()
    serializer_class = FactureStatusSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrAccountant]

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
    permission_classes = [permissions.IsAuthenticated, IsAdminOrAccountant]
    
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
                'client': facture.client.get_full_name(),
                'amount': facture.total_amount,
                'status': 'valid'
            }, status=status.HTTP_200_OK)
            
        except Facture.DoesNotExist:
            return Response({'error': 'Facture non valide'}, status=400)

class QRCodePaymentView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrAccountant]
    
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
                currency='usd',
                payment_method_types=['card'],
                metadata={
                    'facture_id': facture.id,
                    'payment_uuid': str(facture.payment_uuid)
                }
            )
            
            payment, created = Payment.objects.get_or_create(
                facture=facture,
                defaults={
                    'stripe_payment_intent': payment_intent.id,
                    'amount': facture.total_amount,
                    'currency': 'USD'
                }
            )
            
            facture.qr_verified = True
            facture.save()

            facture.status = 'paid'
            facture.payment_date = timezone.now()
            facture.save(update_fields=['status', 'payment_date'])
            
            return Response({
                'client_secret': payment_intent.client_secret,
                'payment_id': payment_intent.id
            }, status=status.HTTP_200_OK)
            
        except Facture.DoesNotExist:
            return Response({'error': 'Facture non valide'}, status=400)

        
class FactureCreateView(generics.CreateAPIView):
    queryset = Facture.objects.all()
    serializer_class = FactureCreateSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrAccountant]

    def perform_create(self, serializer):
        if serializer.validated_data['type'] == 'CLIENT':
            serializer.save(employee=self.request.user)
        else:
            # Calculate tax for non-client factures
            base_amount = serializer.validated_data['base_amount']
            tax_amount = base_amount * Decimal('0.20')
            total_amount = base_amount + tax_amount
            
            serializer.save(
                employee=self.request.user,
                tax_amount=tax_amount,
                total_amount=total_amount
            )

logger = logging.getLogger(__name__)
CLASSIFIER_LOCK = threading.Lock()

@csrf_exempt
def handle_invoice_upload(request):
    """Handle invoice image upload and classification with enhanced validation."""
    if request.method != 'POST':
        logger.warning("Invalid method attempted: %s", request.method)
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    if not request.FILES.get('invoice_image'):
        logger.warning("No invoice image provided in request")
        return JsonResponse({'error': 'No invoice image provided'}, status=400)

    uploaded_file = request.FILES['invoice_image']
    file_meta = {
        'original_name': uploaded_file.name,
        'content_type': uploaded_file.content_type,
        'size': uploaded_file.size
    }

    try:
        # Validate file constraints
        if uploaded_file.size > settings.MAX_UPLOAD_SIZE:
            raise ValidationError(f"File size exceeds {settings.MAX_UPLOAD_SIZE//1024//1024}MB limit")
            
        if not uploaded_file.name.lower().endswith(tuple(settings.ALLOWED_EXTENSIONS)):
            raise ValidationError(f"Invalid file format. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}")

        # Generate secure filename
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        base_name, ext = os.path.splitext(uploaded_file.name)
        safe_name = (
            f"{timestamp}_"
            f"{base_name[:45].encode('ascii', 'ignore').decode().strip('._')}"
            f"{ext.lower()}"
        ).replace(' ', '_').replace('%', '')

        # Ensure upload directory exists
        upload_dir = os.path.join(settings.MEDIA_ROOT, 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, safe_name)

        # Secure file write operation
        try:
            with open(file_path, 'wb+') as destination:
                for chunk in uploaded_file.chunks():
                    destination.write(chunk)
        except IOError as e:
            logger.error("File write error: %s", str(e))
            raise ValidationError("Failed to save uploaded file") from e

        # Validate image integrity
        try:
            with Image.open(file_path) as img:
                img.verify()
                
            # Convert to standardized format
            with Image.open(file_path) as img:
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                    img.save(file_path, quality=85, optimize=True)
        except (UnidentifiedImageError, IOError) as e:
            logger.error("Invalid image file: %s - %s", file_path, str(e))
            os.remove(file_path)
            raise ValidationError("Invalid or corrupted image file") from e

        # Classify with thread-safe model access
        with CLASSIFIER_LOCK:
            classifier = InvoiceClassifier.get_instance()
            try:
                predicted_type, confidence = classifier.predict_with_confidence(file_path)
            except Exception as e:
                logger.error("Classification failed: %s", str(e))
                raise RuntimeError("Error processing image") from e

        # Create database record
        facture = Facture.objects.create(
            type=predicted_type if predicted_type in dict(Facture.TYPE_CHOICES) else 'PURCHASE',
            image=file_path,
            predicted_type=predicted_type,
            status='pending_review' if confidence < settings.CONFIDENCE_THRESHOLD else 'unpaid',
            needs_review=confidence < settings.CONFIDENCE_THRESHOLD,
            original_filename=file_meta['original_name'],
            file_metadata=file_meta,
            processing_metadata={
                'model_version': classifier.model_version,
                'processing_time': classifier.last_processing_time
            }
        )

        return JsonResponse({
            'success': True,
            'facture_id': facture.id,
            'predicted_type': predicted_type,
            'confidence': round(confidence, 4),
            'needs_review': facture.needs_review,
            'file_url': request.build_absolute_uri(facture.image.url) if facture.image else None
        })

    except ValidationError as e:
        logger.warning("Validation error: %s - %s", uploaded_file.name, str(e))
        return JsonResponse({'error': str(e)}, status=400)

    except RuntimeError as e:
        logger.error("Processing error: %s - %s", uploaded_file.name, str(e))
        return JsonResponse({'error': 'Error processing request'}, status=500)

    except Exception as e:
        logger.critical("Unexpected error: %s - %s", uploaded_file.name, str(e), exc_info=True)
        if 'file_path' in locals() and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError as cleanup_error:
                logger.error("Cleanup failed: %s", str(cleanup_error))
        return JsonResponse({
            'error': 'Internal server error',
            'detail': str(e) if settings.DEBUG else None
        }, status=500)
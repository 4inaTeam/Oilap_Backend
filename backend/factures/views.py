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
from reportlab.lib.pagesizes import letter, A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm, inch
from reportlab.lib.colors import black, grey, darkblue
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib import colors
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

        # For non-CLIENT factures, serve existing PDF
        if facture.type != 'CLIENT':
            if not facture.pdf_file:
                return Response(
                    {"error": "PDF not available."},
                    status=status.HTTP_404_NOT_FOUND
                )
            response = HttpResponse(facture.pdf_file.read(), content_type='application/pdf')
            response['Content-Disposition'] = f'filename="facture_{facture.id}.pdf"'
            return response

        # Generate professional PDF for CLIENT factures
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20*mm, bottomMargin=20*mm)
        story = []
        
        # Styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=darkblue,
            spaceAfter=20,
            alignment=2  # Right alignment
        )
        
        normal_style = styles['Normal']
        normal_style.fontSize = 10
        
        # Company header
        header_data = [
            ['', 'Facture'],
            ['', f'Nom de l\'usine'],
            ['', f'REG: 12300012300'],
            ['', f'ma3melFoulen@gmail.com | +216 33 524 415'],
            ['', ''],
            ['', 'Nom de client'],
            [f'NUMÉRO DE FACTURE :', f'FAC-{facture.id:04d}'],
            [f'DATE DE FACTURE :', facture.issue_date.strftime('%d %b %Y')],
        ]
        
        header_table = Table(header_data, colWidths=[3*inch, 3*inch])
        header_table.setStyle(TableStyle([
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (1, 0), (1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (1, 0), (1, 0), 16),
            ('FONTNAME', (1, 1), (1, 3), 'Helvetica'),
            ('FONTSIZE', (1, 1), (1, 3), 9),
            ('FONTNAME', (1, 5), (1, 5), 'Helvetica-Bold'),
            ('FONTSIZE', (1, 5), (1, 5), 12),
            ('FONTNAME', (0, 6), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 6), (-1, -1), 9),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        
        story.append(header_table)
        story.append(Spacer(1, 30))

        # Products table
        if facture.product:
            product_data = [
                ['Produit', 'Quantité', 'Production', 'Prix Unitaire', 'Total']
            ]
            
            # Add product row
            product = facture.product
            unit_price = product.price if hasattr(product, 'price') else facture.base_amount
            quantity = product.quantity if hasattr(product, 'quantity') else 1
            production = f"{quantity} L" if hasattr(product, 'quantity') else "N/A"
            
            product_data.append([
                product.name if hasattr(product, 'name') else f'Product {product.id}',
                f'{quantity} Kg' if hasattr(product, 'quantity') else 'N/A',
                production,
                f'{unit_price} DT',
                f'{facture.base_amount} DT'
            ])
            
            product_table = Table(product_data, colWidths=[2*inch, 1*inch, 1*inch, 1*inch, 1*inch])
            product_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(product_table)
            story.append(Spacer(1, 20))

        # Delivery mode table (if applicable)
        delivery_data = [
            ['Mode de livraison', 'Qty', 'Kilomètre', 'Prix L/Km', 'Total']
        ]
        
        # Add delivery row - you may need to adjust based on your Product model
        delivery_data.append([
            'Livraison assurée',
            '240 L',
            '20 Km',
            '2 DT',
            '40 DT'
        ])
        
        delivery_table = Table(delivery_data, colWidths=[2*inch, 1*inch, 1*inch, 1*inch, 1*inch])
        delivery_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(delivery_table)
        story.append(Spacer(1, 40))

        # Signature and totals section
        signature_totals_data = [
            ['Signature', '', 'Total', f'{facture.base_amount} DT'],
            ['', '', 'TVA', f'{facture.tax_amount} DT'],
            ['', '', 'Frais de carte de crédit (si utilisée) :', '12 DT'],
            ['', '', '', ''],
            ['', '', 'Prix Total:', f'{facture.total_amount} DT'],
        ]
        
        signature_table = Table(signature_totals_data, colWidths=[2*inch, 1.5*inch, 1.5*inch, 1*inch])
        signature_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (0, 0), 12),
            ('FONTNAME', (2, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (2, 0), (-1, -1), 10),
            ('FONTNAME', (2, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (2, -1), (-1, -1), 12),
            ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOX', (2, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (2, -1), (-1, -1), colors.lightgrey),
        ]))
        
        story.append(signature_table)
        story.append(Spacer(1, 40))

        # Payment instructions and QR code
        payment_info = f"""
        INSTRUCTIONS DE PAIEMENT
        
        Nom de l'usine
        SWIFT/IBAN: NZ0201230012
        Numéro de compte: 12-1234-1234256-12
        
        Pour toute question, veuillez nous contacter : ma3melFoulen@gmail.com | +216 33 524 415
        """
        
        payment_para = Paragraph(payment_info, normal_style)
        story.append(payment_para)

        # Add QR code if available
        if facture.qr_code:
            try:
                qr_code_path = facture.qr_code.path
                if os.path.exists(qr_code_path):
                    qr_image = RLImage(qr_code_path, width=1*inch, height=1*inch)
                    qr_data = [[qr_image]]
                    qr_table = Table(qr_data)
                    qr_table.setStyle(TableStyle([
                        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                    ]))
                    story.append(qr_table)
            except Exception as e:
                pass  # QR code loading failed

        # Build PDF
        doc.build(story)
        buffer.seek(0)
        
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'filename="facture_{facture.id}.pdf"'
        return response


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
            # Add your FCM notification function here
            pass


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
                'client': facture.client.get_full_name() if facture.client else 'N/A',
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


# Keep your existing upload handler
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
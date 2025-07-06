from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib.auth import get_user_model
from django.db.models import Sum, Q, Count
from decimal import Decimal
from .models import Facture
from .serializers import FactureSerializer
from .utils import generate_facture_pdf, generate_and_upload_facture_pdf
import stripe
from django.conf import settings
import requests
import logging

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY

User = get_user_model()


class FactureViewSet(viewsets.ModelViewSet):
    serializer_class = FactureSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        if user.role in ['ADMIN', 'EMPLOYEE', 'ACCOUNTANT']:
            queryset = Facture.objects.all()

            # Allow filtering by client_id via query parameter
            client_id = self.request.query_params.get('client_id', None)
            if client_id:
                try:
                    # Validate that the client exists and is actually a client
                    client = User.objects.get(id=client_id, role='CLIENT')
                    queryset = queryset.filter(client=client)
                except User.DoesNotExist:
                    # Return empty queryset if client doesn't exist or isn't a client
                    queryset = Facture.objects.none()

            return queryset
        else:
            # Regular clients can only see their own factures
            return Facture.objects.filter(client=user)

    def create(self, request, *args, **kwargs):
        """Override create to automatically generate PDF after facture creation"""
        response = super().create(request, *args, **kwargs)

        if response.status_code == status.HTTP_201_CREATED:
            try:
                facture_id = response.data.get('id')
                if facture_id:
                    facture = Facture.objects.get(id=facture_id)
                    logger.info(
                        f"Starting PDF generation for facture {facture.facture_number}")

                    pdf_buffer = generate_facture_pdf(facture)
                    if not pdf_buffer:
                        raise Exception("PDF buffer is empty")

                    pdf_url = generate_and_upload_facture_pdf(facture)
                    if pdf_url:
                        facture.pdf_url = pdf_url
                        facture.save()
                        response.data['pdf_url'] = pdf_url
                        logger.info(
                            f"PDF generated and uploaded successfully: {pdf_url}")
                    else:
                        raise Exception("Failed to upload PDF to Cloudinary")

            except Exception as e:
                logger.error(
                    f"PDF Generation Error for facture {facture_id}: {str(e)}")
                response.data['pdf_generation_error'] = str(e)

        return response

    @action(detail=False, methods=['get'])
    def total_revenue(self, request):
        """Calculate total revenue from paid factures"""
        try:
            user = request.user

            # Check permissions - only ADMIN, EMPLOYEE, and ACCOUNTANT can view total revenue
            if user.role not in ['ADMIN', 'EMPLOYEE', 'ACCOUNTANT']:
                return Response(
                    {'error': 'You do not have permission to view total revenue.'},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Get query parameters for filtering
            client_id = request.query_params.get('client_id', None)
            date_from = request.query_params.get('date_from', None)
            date_to = request.query_params.get('date_to', None)

            # Base queryset - only paid factures
            queryset = Facture.objects.filter(payment_status='paid')

            # Apply client filter if provided
            if client_id:
                try:
                    client = User.objects.get(id=client_id, role='CLIENT')
                    queryset = queryset.filter(client=client)
                except User.DoesNotExist:
                    return Response(
                        {'error': 'Client not found or invalid client ID.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Apply date filters if provided
            if date_from:
                queryset = queryset.filter(created_at__date__gte=date_from)
            if date_to:
                queryset = queryset.filter(created_at__date__lte=date_to)

            # Calculate totals
            revenue_data = queryset.aggregate(
                total_revenue=Sum('final_total'),
                total_amount_before_tax=Sum('total_amount'),
                total_tva=Sum('tva_amount'),
                facture_count=Count('id')
            )

            # Handle case where no paid factures exist
            total_revenue = revenue_data['total_revenue'] or Decimal('0.00')
            total_amount_before_tax = revenue_data['total_amount_before_tax'] or Decimal(
                '0.00')
            total_tva = revenue_data['total_tva'] or Decimal('0.00')
            facture_count = revenue_data['facture_count'] or 0

            # Prepare response data
            response_data = {
                'total_revenue': float(total_revenue),
                'total_amount_before_tax': float(total_amount_before_tax),
                'total_tva': float(total_tva),
                'paid_factures_count': facture_count,
                'filters_applied': {
                    'client_id': client_id,
                    'date_from': date_from,
                    'date_to': date_to
                }
            }

            # Add client info if filtered by client
            if client_id:
                try:
                    client = User.objects.get(id=client_id, role='CLIENT')
                    response_data['client_info'] = {
                        'id': client.id,
                        'username': client.username,
                        'email': getattr(client, 'email', ''),
                        'first_name': getattr(client, 'first_name', ''),
                        'last_name': getattr(client, 'last_name', '')
                    }
                except User.DoesNotExist:
                    pass

            logger.info(
                f"Total revenue calculated: {total_revenue} from {facture_count} paid factures")
            return Response(response_data)

        except Exception as e:
            logger.error(f"Error calculating total revenue: {str(e)}")
            return Response(
                {'error': 'An error occurred while calculating total revenue.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def download_pdf(self, request, pk=None):
        """Download facture PDF from Cloudinary or generate new one"""
        try:
            facture = self.get_object()
            logger.info(
                f"Download PDF requested for facture {facture.facture_number}")

            if hasattr(facture, 'pdf_url') and facture.pdf_url:
                logger.info(f"Redirecting to existing PDF: {facture.pdf_url}")
                return HttpResponseRedirect(facture.pdf_url)

            logger.info("No existing PDF found, generating new one")
            pdf_url = generate_and_upload_facture_pdf(facture)
            if pdf_url:
                logger.info(f"New PDF generated, redirecting to: {pdf_url}")
                return HttpResponseRedirect(pdf_url)

            logger.info("Cloudinary upload failed, serving PDF directly")
            pdf_buffer = generate_facture_pdf(facture)
            response = HttpResponse(
                pdf_buffer.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="facture_{facture.facture_number}.pdf"'
            return response

        except Exception as e:
            logger.error(f"Error in download_pdf: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def regenerate_pdf(self, request, pk=None):
        """Regenerate and re-upload PDF to Cloudinary"""
        try:
            facture = self.get_object()
            logger.info(
                f"PDF regeneration requested for facture {facture.facture_number}")

            pdf_url = generate_and_upload_facture_pdf(
                facture, force_regenerate=True)

            if pdf_url:
                logger.info(f"PDF regenerated successfully: {pdf_url}")
                return Response({
                    'message': 'PDF regenerated successfully',
                    'pdf_url': pdf_url,
                    'pdf_public_id': getattr(facture, 'pdf_public_id', None)
                })
            else:
                logger.error("Failed to regenerate PDF")
                return Response({'error': 'Failed to generate PDF'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            logger.error(f"Error regenerating PDF: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def view_pdf(self, request, pk=None):
        """Get PDF URL for viewing in browser with access control"""
        try:
            facture = self.get_object()
            user = request.user

            if user.role not in ['ADMIN', 'ACCOUNTANT']:
                if not facture.client or facture.client != user:
                    return Response({'error': 'You do not have permission to view this facture.'}, status=status.HTTP_403_FORBIDDEN)

            logger.info(
                f"PDF view requested for facture {facture.facture_number}")

            if not hasattr(facture, 'pdf_url') or not facture.pdf_url:
                logger.info("PDF doesn't exist, generating new one")
                pdf_url = generate_and_upload_facture_pdf(facture)
                if not pdf_url:
                    logger.error("Failed to generate PDF for viewing")
                    return Response({'error': 'Failed to generate PDF'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            return Response({
                'pdf_url': facture.pdf_url,
                'facture_number': facture.facture_number
            })

        except Exception as e:
            logger.error(f"Error in view_pdf: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def debug_facture(self, request):
        """Debug endpoint to test PDF generation"""
        try:
            facture = Facture.objects.first()
            if not facture:
                return Response({'error': 'No factures found'}, status=status.HTTP_404_NOT_FOUND)

            logger.info(
                f"Debug: Testing PDF generation for facture {facture.facture_number}")

            debug_info = {
                'facture_id': facture.id,
                'facture_number': facture.facture_number,
                'client': str(facture.client) if facture.client else 'No client',
                'created_at': facture.created_at,
                'has_products': hasattr(facture, 'products') and facture.products.exists(),
                'product_count': facture.products.count() if hasattr(facture, 'products') else 0,
                'total_amount': getattr(facture, 'total_amount', 'Not set'),
                'final_total': getattr(facture, 'final_total', 'Not set'),
                'existing_pdf_url': getattr(facture, 'pdf_url', 'None'),
            }

            logger.info("Debug: Attempting PDF generation...")
            pdf_url = generate_and_upload_facture_pdf(
                facture, force_regenerate=True)

            debug_info['pdf_generation_successful'] = pdf_url is not None
            debug_info['new_pdf_url'] = pdf_url

            return Response(debug_info)

        except Exception as e:
            logger.error(f"Debug error: {str(e)}")
            return Response({'error': str(e), 'debug': True}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def create_payment_intent(self, request, pk=None):
        """Create Stripe payment intent for facture"""
        try:
            facture = self.get_object()
            logger.info(
                f"Payment intent requested for facture {facture.facture_number}")

            intent = stripe.PaymentIntent.create(
                amount=int(facture.final_total * 100),
                currency='usd',
                metadata={
                    'facture_id': facture.id,
                    'facture_number': facture.facture_number,
                    'client_id': facture.client.id
                }
            )

            facture.stripe_payment_intent = intent.id
            facture.save()

            logger.info(f"Payment intent created: {intent.id}")
            return Response({
                'client_secret': intent.client_secret,
                'payment_intent_id': intent.id
            })
        except Exception as e:
            logger.error(f"Error creating payment intent: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def confirm_payment(self, request, pk=None):
        """Confirm payment and update facture status"""
        try:
            facture = self.get_object()
            payment_intent_id = request.data.get('payment_intent_id')
            logger.info(
                f"Payment confirmation for facture {facture.facture_number}, intent: {payment_intent_id}")

            intent = stripe.PaymentIntent.retrieve(payment_intent_id)

            if intent.status == 'succeeded':
                facture.payment_status = 'paid'
                facture.save()

                if hasattr(facture, 'products'):
                    updated_count = facture.products.filter(
                        payement='unpaid').update(payement='paid')
                    logger.info(
                        f"Updated {updated_count} products to paid status")

                logger.info(
                    f"Payment confirmed for facture {facture.facture_number}")
                return Response({'status': 'Payment confirmed'})
            else:
                logger.warning(
                    f"Payment not succeeded, status: {intent.status}")
                return Response({'error': 'Payment not confirmed'}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f"Error confirming payment: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

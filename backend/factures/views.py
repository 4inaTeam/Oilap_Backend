from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.http import HttpResponse, HttpResponseRedirect
from .models import Facture
from .serializers import FactureSerializer
from .utils import generate_facture_pdf, generate_and_upload_facture_pdf
import stripe
from django.conf import settings
import requests
import logging

# Set up logging
logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY


class FactureViewSet(viewsets.ModelViewSet):
    serializer_class = FactureSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['ADMIN', 'EMPLOYEE', 'ACCOUNTANT']:
            return Facture.objects.all()
        else:
            return Facture.objects.filter(client=user)

    def create(self, request, *args, **kwargs):
        """Override create to automatically generate PDF after facture creation"""
        response = super().create(request, *args, **kwargs)

        if response.status_code == status.HTTP_201_CREATED:
            try:
                # Get the created facture
                facture_id = response.data.get('id')
                if facture_id:
                    facture = Facture.objects.get(id=facture_id)

                    # Generate PDF automatically
                    logger.info(
                        f"Auto-generating PDF for newly created facture {facture.facture_number}")
                    pdf_url = generate_and_upload_facture_pdf(facture)

                    if pdf_url:
                        # Update response data with PDF URL
                        response.data['pdf_url'] = pdf_url
                        logger.info(
                            f"PDF auto-generated successfully for facture {facture.facture_number}")
                    else:
                        logger.warning(
                            f"Failed to auto-generate PDF for facture {facture.facture_number}")

            except Exception as e:
                logger.error(
                    f"Error auto-generating PDF after facture creation: {str(e)}")
                # Don't fail the creation, just log the error

        return response

    @action(detail=True, methods=['get'])
    def download_pdf(self, request, pk=None):
        """Download facture PDF from Cloudinary or generate new one"""
        try:
            facture = self.get_object()
            logger.info(
                f"Download PDF requested for facture {facture.facture_number}")

            # If PDF exists on Cloudinary, redirect to it
            if hasattr(facture, 'pdf_url') and facture.pdf_url:
                logger.info(f"Redirecting to existing PDF: {facture.pdf_url}")
                return HttpResponseRedirect(facture.pdf_url)

            # If no PDF exists, generate new one and upload to Cloudinary
            logger.info("No existing PDF found, generating new one")
            pdf_url = generate_and_upload_facture_pdf(facture)
            if pdf_url:
                logger.info(f"New PDF generated, redirecting to: {pdf_url}")
                return HttpResponseRedirect(pdf_url)

            # Fallback: generate PDF directly and serve it
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
        """Get PDF URL for viewing in browser"""
        try:
            facture = self.get_object()
            logger.info(
                f"PDF view requested for facture {facture.facture_number}")

            if not hasattr(facture, 'pdf_url') or not facture.pdf_url:
                # Generate PDF if it doesn't exist
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
            # Get a sample facture or create a test one
            facture = Facture.objects.first()
            if not facture:
                return Response({'error': 'No factures found'}, status=status.HTTP_404_NOT_FOUND)

            logger.info(
                f"Debug: Testing PDF generation for facture {facture.facture_number}")

            # Check facture data
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

            # Test PDF generation
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

            # Create payment intent
            intent = stripe.PaymentIntent.create(
                amount=int(facture.final_total * 100),  # Convert to cents
                currency='usd',  # Change to your currency
                metadata={
                    'facture_id': facture.id,
                    'facture_number': facture.facture_number,
                    'client_id': facture.client.id
                }
            )

            # Save payment intent ID
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

            # Verify payment with Stripe
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)

            if intent.status == 'succeeded':
                # Update facture status
                facture.payment_status = 'paid'
                facture.save()

                # Update all products in this facture to paid
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

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import rest_framework as django_filters
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
import traceback

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY

User = get_user_model()


class FacturePagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response({
            'count': self.page.paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'total_pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
            'page_size': self.page_size,
            'results': data
        })


class FactureFilter(django_filters.FilterSet):
    # Status filtering - update these choices according to your model
    statut = django_filters.ChoiceFilter(
        field_name='payment_status',
        choices=[
            ('paid', 'Paid'),
            ('unpaid', 'Unpaid'),
            ('pending', 'Pending'),
            ('overdue', 'Overdue'),
            ('cancelled', 'Cancelled'),
        ]
    )

    # Alternative if you have a different status field
    payment_status = django_filters.ChoiceFilter(
        choices=[
            ('paid', 'Paid'),
            ('unpaid', 'Unpaid'),
            ('pending', 'Pending'),
            ('overdue', 'Overdue'),
            ('cancelled', 'Cancelled'),
        ]
    )

    # Amount filtering
    montant_min = django_filters.NumberFilter(
        field_name='final_total', lookup_expr='gte')
    montant_max = django_filters.NumberFilter(
        field_name='final_total', lookup_expr='lte')
    montant_exact = django_filters.NumberFilter(
        field_name='final_total', lookup_expr='exact')

    # Alternative amount fields
    total_amount_min = django_filters.NumberFilter(
        field_name='total_amount', lookup_expr='gte')
    total_amount_max = django_filters.NumberFilter(
        field_name='total_amount', lookup_expr='lte')

    # Date filtering
    date_creation_after = django_filters.DateFilter(
        field_name='created_at', lookup_expr='gte')
    date_creation_before = django_filters.DateFilter(
        field_name='created_at', lookup_expr='lte')
    date_echeance_after = django_filters.DateFilter(
        field_name='due_date', lookup_expr='gte')
    date_echeance_before = django_filters.DateFilter(
        field_name='due_date', lookup_expr='lte')

    # Client filtering (for admin/employee/accountant)
    client_id = django_filters.NumberFilter(field_name='client__id')
    client_cin = django_filters.CharFilter(
        field_name='client__cin', lookup_expr='icontains')
    client_username = django_filters.CharFilter(
        field_name='client__username', lookup_expr='icontains')
    client_email = django_filters.CharFilter(
        field_name='client__email', lookup_expr='icontains')

    # Facture number filtering
    facture_number = django_filters.CharFilter(
        field_name='facture_number', lookup_expr='icontains')

    class Meta:
        model = Facture
        fields = [
            'statut',
            'payment_status',
            'montant_min',
            'montant_max',
            'montant_exact',
            'total_amount_min',
            'total_amount_max',
            'date_creation_after',
            'date_creation_before',
            'date_echeance_after',
            'date_echeance_before',
            'client_id',
            'client_cin',
            'client_username',
            'client_email',
            'facture_number'
        ]


class FactureSearchFilter(filters.SearchFilter):
    """Custom search filter for Facture model"""

    def filter_queryset(self, request, queryset, view):
        search_param = self.get_search_terms(request)
        if not search_param:
            return queryset

        search_query = ' '.join(search_param)

        # Build search query for different fields
        search_conditions = Q()

        # Search by ID
        if search_query.isdigit():
            search_conditions |= Q(id=int(search_query))

        # Search by facture number
        search_conditions |= Q(facture_number__icontains=search_query)

        # Search by client information
        search_conditions |= Q(client__username__icontains=search_query)
        search_conditions |= Q(client__email__icontains=search_query)
        search_conditions |= Q(client__cin__icontains=search_query)
        search_conditions |= Q(client__first_name__icontains=search_query)
        search_conditions |= Q(client__last_name__icontains=search_query)

        # Search by amount (if numeric)
        try:
            amount = float(search_query)
            search_conditions |= Q(final_total=amount)
            search_conditions |= Q(total_amount=amount)
        except ValueError:
            pass

        # Search by status
        search_conditions |= Q(payment_status__icontains=search_query)

        # Search by description or notes (if you have these fields)
        if hasattr(queryset.model, 'description'):
            search_conditions |= Q(description__icontains=search_query)
        if hasattr(queryset.model, 'notes'):
            search_conditions |= Q(notes__icontains=search_query)

        return queryset.filter(search_conditions).distinct()


class FactureViewSet(viewsets.ModelViewSet):
    serializer_class = FactureSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = FacturePagination
    filter_backends = [DjangoFilterBackend,
                       FactureSearchFilter, filters.OrderingFilter]
    filterset_class = FactureFilter
    search_fields = []  # We use custom search filter
    ordering_fields = ['id', 'created_at', 'due_date', 'final_total',
                       'total_amount', 'payment_status', 'facture_number']
    ordering = ['-created_at']  # Default ordering

    def get_queryset(self):
        user = self.request.user

        if user.role in ['ADMIN', 'EMPLOYEE', 'ACCOUNTANT']:
            queryset = Facture.objects.all()

            # Allow filtering by client_id via query parameter (backward compatibility)
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

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

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
                logger.error(f"Traceback: {traceback.format_exc()}")
                response.data['pdf_generation_error'] = str(e)

        return response

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get facture statistics with filtering support"""
        try:
            user = request.user

            # Check permissions
            if user.role not in ['ADMIN', 'EMPLOYEE', 'ACCOUNTANT']:
                return Response(
                    {'error': 'You do not have permission to view statistics.'},
                    status=status.HTTP_403_FORBIDDEN
                )

            queryset = self.filter_queryset(self.get_queryset())

            # Basic statistics
            total_factures = queryset.count()
            total_revenue = queryset.aggregate(
                total=Sum('final_total'))['total'] or 0
            total_amount_before_tax = queryset.aggregate(
                total=Sum('total_amount'))['total'] or 0

            # Status-based statistics
            status_stats = {}
            for status_choice in ['paid', 'unpaid', 'pending', 'overdue', 'cancelled']:
                status_queryset = queryset.filter(payment_status=status_choice)
                status_stats[status_choice] = {
                    'count': status_queryset.count(),
                    'total_amount': status_queryset.aggregate(total=Sum('final_total'))['total'] or 0
                }

            # Recent factures
            recent_factures = queryset.order_by('-created_at')[:10]

            stats = {
                'total_factures': total_factures,
                'total_revenue': float(total_revenue),
                'total_amount_before_tax': float(total_amount_before_tax),
                'by_status': status_stats,
                'recent_factures_count': recent_factures.count(),
                'filters_applied': dict(request.query_params)
            }

            return Response(stats)

        except Exception as e:
            logger.error(f"Error calculating statistics: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return Response(
                {'error': 'An error occurred while calculating statistics.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def by_status(self, request):
        """Get factures grouped by status with current filters applied"""
        try:
            user = request.user

            if user.role not in ['ADMIN', 'EMPLOYEE', 'ACCOUNTANT']:
                return Response(
                    {'error': 'You do not have permission to view status breakdown.'},
                    status=status.HTTP_403_FORBIDDEN
                )

            queryset = self.filter_queryset(self.get_queryset())
            status_counts = {}

            for status_choice in ['paid', 'unpaid', 'pending', 'overdue', 'cancelled']:
                count = queryset.filter(payment_status=status_choice).count()
                status_counts[status_choice] = count

            return Response(status_counts)

        except Exception as e:
            logger.error(f"Error getting status breakdown: {str(e)}")
            return Response(
                {'error': 'An error occurred while getting status breakdown.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def total_revenue(self, request):
        """Calculate total revenue from paid factures with enhanced filtering"""
        try:
            user = request.user

            # Check permissions - only ADMIN, EMPLOYEE, and ACCOUNTANT can view total revenue
            if user.role not in ['ADMIN', 'EMPLOYEE', 'ACCOUNTANT']:
                return Response(
                    {'error': 'You do not have permission to view total revenue.'},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Apply all filters from the filterset
            queryset = self.filter_queryset(self.get_queryset())

            # Additional legacy filter support
            client_id = request.query_params.get('client_id', None)
            date_from = request.query_params.get('date_from', None)
            date_to = request.query_params.get('date_to', None)

            # Base queryset - only paid factures
            queryset = queryset.filter(payment_status='paid')

            # Apply legacy client filter if provided
            if client_id:
                try:
                    client = User.objects.get(id=client_id, role='CLIENT')
                    queryset = queryset.filter(client=client)
                except User.DoesNotExist:
                    return Response(
                        {'error': 'Client not found or invalid client ID.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Apply legacy date filters if provided
            if date_from:
                queryset = queryset.filter(created_at__date__gte=date_from)
            if date_to:
                queryset = queryset.filter(created_at__date__lte=date_to)

            # Calculate totals
            revenue_data = queryset.aggregate(
                total_revenue=Sum('final_total'),
                total_amount_before_tax=Sum('total_amount'),
                total_tva=Sum('tva_amount') if hasattr(Facture, 'tva_amount') else Sum(
                    'final_total') - Sum('total_amount'),
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
                'filters_applied': dict(request.query_params)
            }

            # Add client info if filtered by client
            if client_id:
                try:
                    client = User.objects.get(id=client_id, role='CLIENT')
                    response_data['client_info'] = {
                        'id': client.id,
                        'username': client.username,
                        'email': getattr(client, 'email', ''),
                        'cin': getattr(client, 'cin', ''),
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
            logger.error(f"Traceback: {traceback.format_exc()}")
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

            # Check if PDF exists and is accessible
            if hasattr(facture, 'pdf_url') and facture.pdf_url:
                logger.info(f"Redirecting to existing PDF: {facture.pdf_url}")
                return HttpResponseRedirect(facture.pdf_url)

            # Generate new PDF if none exists
            logger.info("No existing PDF found, generating new one")
            pdf_url = generate_and_upload_facture_pdf(facture)
            if pdf_url:
                logger.info(f"New PDF generated, redirecting to: {pdf_url}")
                return HttpResponseRedirect(pdf_url)

            # Fallback: serve PDF directly
            logger.info("Cloudinary upload failed, serving PDF directly")
            pdf_buffer = generate_facture_pdf(facture)
            if pdf_buffer:
                response = HttpResponse(
                    pdf_buffer.getvalue(), content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename="facture_{facture.facture_number}.pdf"'
                return response
            else:
                raise Exception("Failed to generate PDF buffer")

        except Exception as e:
            logger.error(f"Error in download_pdf: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
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
            logger.error(f"Traceback: {traceback.format_exc()}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'])
    def view_pdf(self, request, pk=None):
        """Get PDF URL for viewing in browser with access control"""
        try:
            # Get the facture object
            try:
                facture = self.get_object()
                logger.info(
                    f"PDF view requested for facture {facture.facture_number}")
            except Exception as e:
                logger.error(f"Error getting facture object: {str(e)}")
                return Response({'error': 'Facture not found'}, status=status.HTTP_404_NOT_FOUND)

            # Check permissions
            user = request.user
            logger.info(
                f"User {user.username} (role: {user.role}) requesting PDF for facture {facture.facture_number}")

            # Allow ADMIN and ACCOUNTANT to view all factures
            if user.role not in ['ADMIN', 'ACCOUNTANT']:
                # Check if user is the client of this facture
                if not facture.client:
                    logger.error(
                        f"Facture {facture.facture_number} has no client assigned")
                    return Response({'error': 'Facture has no client assigned'}, status=status.HTTP_400_BAD_REQUEST)

                if facture.client != user:
                    logger.warning(
                        f"User {user.username} denied access to facture {facture.facture_number} (belongs to {facture.client.username})")
                    return Response({'error': 'You do not have permission to view this facture.'}, status=status.HTTP_403_FORBIDDEN)

            # Check if PDF already exists
            if hasattr(facture, 'pdf_url') and facture.pdf_url:
                logger.info(f"Returning existing PDF URL: {facture.pdf_url}")
                return Response({
                    'pdf_url': facture.pdf_url,
                    'facture_number': facture.facture_number
                })

            # Generate PDF if it doesn't exist
            logger.info("PDF doesn't exist, generating new one")
            try:
                pdf_url = generate_and_upload_facture_pdf(facture)
                if pdf_url:
                    logger.info(f"PDF generated successfully: {pdf_url}")
                    return Response({
                        'pdf_url': pdf_url,
                        'facture_number': facture.facture_number
                    })
                else:
                    logger.error("Failed to generate PDF for viewing")
                    return Response({'error': 'Failed to generate PDF'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            except Exception as pdf_error:
                logger.error(f"Error generating PDF: {str(pdf_error)}")
                logger.error(
                    f"PDF generation traceback: {traceback.format_exc()}")
                return Response({'error': f'Failed to generate PDF: {str(pdf_error)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            logger.error(f"Error in view_pdf: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return Response({'error': f'Internal server error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
            logger.error(f"Debug traceback: {traceback.format_exc()}")
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
            logger.error(f"Traceback: {traceback.format_exc()}")
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
            logger.error(f"Traceback: {traceback.format_exc()}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

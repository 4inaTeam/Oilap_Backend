from django.views.decorators.http import require_http_methods
import logging
from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import Q
from django.conf import settings
import csv
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import inch

from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.http import JsonResponse

from .models import Product
from .serializers import ProductSerializer
from users.permissions import IsEmployee, IsAdmin, IsClient
from users.models import CustomUser
from rest_framework.exceptions import ValidationError
from rest_framework.exceptions import NotFound
from django.db.models import Sum, Count, Q
from django.db.models.functions import Coalesce

# Cache imports
from django.core.cache import cache
import hashlib
import json

logger = logging.getLogger(__name__)

# Simple cache manager for products
class ProductCacheManager:
    @staticmethod
    def generate_cache_key(prefix, *args, **kwargs):
        key_parts = [prefix]
        key_parts.extend([str(arg) for arg in args])
        if kwargs:
            sorted_kwargs = sorted(kwargs.items())
            kwargs_str = json.dumps(sorted_kwargs, sort_keys=True)
            key_parts.append(hashlib.md5(kwargs_str.encode()).hexdigest()[:8])
        return ':'.join(key_parts)

    @staticmethod
    def get_cache(prefix, *args, **kwargs):
        key = ProductCacheManager.generate_cache_key(prefix, *args, **kwargs)
        return cache.get(key)

    @staticmethod
    def set_cache(prefix, data, timeout, *args, **kwargs):
        key = ProductCacheManager.generate_cache_key(prefix, *args, **kwargs)
        return cache.set(key, data, timeout)

    @staticmethod
    def delete_cache(prefix, *args, **kwargs):
        key = ProductCacheManager.generate_cache_key(prefix, *args, **kwargs)
        return cache.delete(key)

    @staticmethod
    def clear_user_related_cache(user_id):
        """Clear all cache entries related to a specific user"""
        keys_to_delete = [
            f'products_list_{user_id}',
            f'client_products_{user_id}',
            'product_stats',
            'total_quantity',
            'origin_percentages'
        ]
        for key in keys_to_delete:
            cache.delete(key)

    @staticmethod
    def clear_all_product_cache():
        """Clear all product-related cache"""
        # Clear common cache keys
        cache_keys = [
            'product_stats',
            'total_quantity', 
            'total_quantity_with_waste',
            'origin_percentages',
            'products_list',
            'client_products'
        ]
        for key in cache_keys:
            cache.delete(key)


class IsAdminOrEmployee(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role in ['ADMIN', 'EMPLOYEE']


class ProductCreateView(generics.CreateAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrEmployee]

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        
        if response.status_code == status.HTTP_201_CREATED:
            # Clear relevant caches after product creation
            ProductCacheManager.clear_all_product_cache()
            
            # Clear user-specific caches if applicable
            product_data = response.data
            if 'client' in product_data:
                client_id = product_data.get('client')
                if client_id:
                    ProductCacheManager.clear_user_related_cache(client_id)
            
            logger.info(f"Cache cleared after product creation: {product_data.get('id')}")
            
        return response


class ProductRetrieveView(generics.RetrieveAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        """Override to apply role-based access control"""
        obj = super().get_object()
        user = self.request.user

        if user.role == 'CLIENT':
            # Clients can only view their own products
            if obj.client != user:
                raise permissions.PermissionDenied(
                    'You do not have permission to access this product'
                )
        elif user.role not in ['ADMIN', 'EMPLOYEE', 'ACCOUNTANT']:
            raise permissions.PermissionDenied(
                'You do not have permission to access products'
            )

        return obj

    def retrieve(self, request, *args, **kwargs):
        """Override to add caching for individual product retrieval"""
        product_id = kwargs.get('pk')
        user_id = request.user.id
        
        # Try cache first
        cached_product = ProductCacheManager.get_cache('product_detail', product_id, user_id)
        if cached_product:
            logger.info(f"Cache hit for product detail: {product_id}, user: {user_id}")
            return Response(cached_product)
        
        # Get data using parent method
        response = super().retrieve(request, *args, **kwargs)
        
        # Cache for 15 minutes if successful
        if response.status_code == 200:
            ProductCacheManager.set_cache('product_detail', response.data, 900, product_id, user_id)
            logger.info(f"Cache set for product detail: {product_id}, user: {user_id}")
        
        return response


class ProductUpdateView(generics.UpdateAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrEmployee]

    def perform_update(self, serializer):
        instance = self.get_object()
        old_status = instance.status

        logger.info(
            f"Updating product {instance.id} - Current status: {old_status}")

        if instance.status == 'done':
            raise ValidationError(
                "Cannot update a product with 'done' status.")

        new_status = serializer.validated_data.get('status', instance.status)
        logger.info(f"New status for product {instance.id}: {new_status}")

        # Set end_time when status changes to done
        if new_status == 'done':
            serializer.validated_data['end_time'] = timezone.now()
            logger.info(f"Setting end_time to now for product {instance.id}")

        # Check permissions for status updates
        if 'status' in serializer.validated_data:
            if self.request.user.role not in ['EMPLOYEE', 'ADMIN']:
                raise ValidationError(
                    "Only employees or admins can update the status of a product.")

        # Handle 'doing' status restrictions
        if instance.status == 'doing':
            if new_status != 'done':
                raise ValidationError(
                    "Products in 'doing' status can only be marked as 'done'.")

            # When transitioning from 'doing' to 'done', only allow status change
            validated_data_copy = serializer.validated_data.copy()
            for field in list(validated_data_copy.keys()):
                if field not in ['status', 'end_time']:  # Allow end_time to be updated
                    del validated_data_copy[field]

            serializer.validated_data.clear()
            serializer.validated_data.update(validated_data_copy)

        # Save the instance
        saved_instance = serializer.save()
        logger.info(
            f"Product {saved_instance.id} updated successfully - Status: {saved_instance.status}, Payment: {saved_instance.payement}")

        return saved_instance

    def update(self, request, *args, **kwargs):
        """Override to clear cache after update"""
        response = super().update(request, *args, **kwargs)
        
        if response.status_code == 200:
            product_id = kwargs.get('pk')
            
            # Clear all product-related caches
            ProductCacheManager.clear_all_product_cache()
            
            # Clear specific product detail cache
            ProductCacheManager.delete_cache('product_detail', product_id)
            
            # Clear user-related caches
            try:
                product = Product.objects.get(id=product_id)
                if product.client:
                    ProductCacheManager.clear_user_related_cache(product.client.id)
            except Product.DoesNotExist:
                pass
            
            logger.info(f"Cache cleared after product update: {product_id}")
            
        return response


class CancelProductView(generics.UpdateAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrEmployee]

    def perform_update(self, serializer):
        instance = self.get_object()

        if instance.status != 'pending':
            raise ValidationError(
                "Can only cancel products in 'pending' status.")

        serializer.validated_data['status'] = 'canceled'
        serializer.save()

    def update(self, request, *args, **kwargs):
        """Override to clear cache after cancellation"""
        response = super().update(request, *args, **kwargs)
        
        if response.status_code == 200:
            product_id = kwargs.get('pk')
            
            # Clear caches after cancellation
            ProductCacheManager.clear_all_product_cache()
            ProductCacheManager.delete_cache('product_detail', product_id)
            
            logger.info(f"Cache cleared after product cancellation: {product_id}")
            
        return response


class ProductListView(generics.ListAPIView):
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated,
                          IsEmployee | IsAdmin | IsClient]

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'role') and user.role in ['ADMIN', 'EMPLOYEE']:
            return Product.objects.all()
        return Product.objects.filter(client=user)

    def list(self, request, *args, **kwargs):
        """Override to add caching"""
        user_id = request.user.id
        user_role = request.user.role
        
        # Create cache key including query parameters
        query_params = dict(request.GET)
        query_hash = hashlib.md5(json.dumps(query_params, sort_keys=True).encode()).hexdigest()[:8]
        
        # Try cache first
        cached_result = ProductCacheManager.get_cache('products_list', user_id, user_role, query_hash)
        if cached_result:
            logger.info(f"Cache hit for product list: user {user_id}")
            return Response(cached_result)
        
        # Get data using parent method
        response = super().list(request, *args, **kwargs)
        
        # Cache for 10 minutes if successful
        if response.status_code == 200:
            ProductCacheManager.set_cache('products_list', response.data, 600, user_id, user_role, query_hash)
            logger.info(f"Cache set for product list: user {user_id}")
        
        return response


class ClientProductListView(generics.ListAPIView):
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated, IsClient]

    def get_queryset(self):
        return Product.objects.filter(client=self.request.user)\
            .select_related('client', 'created_by')\
            .order_by('-created_at')

    def list(self, request, *args, **kwargs):
        """Override to add caching for client products"""
        user_id = request.user.id
        
        # Try cache first
        cached_result = ProductCacheManager.get_cache('client_products', user_id)
        if cached_result:
            logger.info(f"Cache hit for client products: user {user_id}")
            return Response(cached_result)
        
        # Get data using parent method
        response = super().list(request, *args, **kwargs)
        
        # Cache for 5 minutes if successful
        if response.status_code == 200:
            ProductCacheManager.set_cache('client_products', response.data, 300, user_id)
            logger.info(f"Cache set for client products: user {user_id}")
        
        return response


class SearchProductByStatus(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrEmployee]

    def get(self, request, status):
        try:
            # Check cache first
            cached_result = ProductCacheManager.get_cache('products_by_status', status)
            if cached_result:
                logger.info(f"Cache hit for products by status: {status}")
                return Response(cached_result)
            
            products = Product.objects.filter(status=status)
            if not products.exists():
                return Response({"message": "No products found with this status."}, status=404)

            serializer = ProductSerializer(products, many=True)
            result_data = serializer.data
            
            # Cache for 5 minutes
            ProductCacheManager.set_cache('products_by_status', result_data, 300, status)
            logger.info(f"Cache set for products by status: {status}")
            
            return Response(result_data)
        except Product.DoesNotExist:
            return Response({"message": "Product not found."}, status=404)


class AdminClientProductListView(generics.ListAPIView):
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrEmployee]

    def get_queryset(self):
        client_id = self.kwargs['client_id']
        try:
            client = CustomUser.objects.get(id=client_id, role='CLIENT')
        except CustomUser.DoesNotExist:
            raise NotFound(detail="Client not found or invalid client role")

        return Product.objects.filter(client=client)

    def list(self, request, *args, **kwargs):
        """Override to add caching for admin client product list"""
        client_id = self.kwargs['client_id']
        user_id = request.user.id
        
        # Try cache first
        cached_result = ProductCacheManager.get_cache('admin_client_products', client_id, user_id)
        if cached_result:
            logger.info(f"Cache hit for admin client products: client {client_id}, user {user_id}")
            return Response(cached_result)
        
        # Get data using parent method
        response = super().list(request, *args, **kwargs)
        
        # Cache for 10 minutes if successful
        if response.status_code == 200:
            ProductCacheManager.set_cache('admin_client_products', response.data, 600, client_id, user_id)
            logger.info(f"Cache set for admin client products: client {client_id}, user {user_id}")
        
        return response


class ProductReportView(APIView):
    """
    Generate and download product reports in CSV or PDF format
    - Admins and employees can filter by any client and see all products
    - Clients can only see their own products
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            format_type = request.GET.get('format', 'csv').lower()
            status_filter = request.GET.get('status', '')
            client_filter = request.GET.get('client', '')
            date_from = request.GET.get('date_from', '')
            date_to = request.GET.get('date_to', '')
            quality_filter = request.GET.get('quality', '')

            # Create cache key for reports
            report_params = {
                'format': format_type,
                'status': status_filter,
                'client': client_filter,
                'date_from': date_from,
                'date_to': date_to,
                'quality': quality_filter,
                'user_id': request.user.id,
                'user_role': request.user.role
            }
            report_hash = hashlib.md5(json.dumps(report_params, sort_keys=True).encode()).hexdigest()[:8]
            
            # For reports, we cache for shorter time due to file nature
            cached_report = ProductCacheManager.get_cache('product_report', report_hash)
            if cached_report:
                logger.info(f"Cache hit for product report: {report_hash}")
                # Note: For file responses, you might want to handle this differently
                # This is just for demonstration
            
            # Base queryset with select_related for performance
            queryset = Product.objects.all().select_related('client', 'created_by')

            # Apply role-based filtering
            user = request.user
            if user.role == 'CLIENT':
                # Clients can only see their own products
                queryset = queryset.filter(client=user)
                # Ignore client_filter parameter for clients (security)
                client_filter = ''
            elif user.role in ['ADMIN', 'EMPLOYEE', 'ACCOUNTANT']:
                # Admin/Employee/Accountant can see all products and filter by client
                if client_filter:
                    queryset = queryset.filter(
                        client__username__icontains=client_filter)
            else:
                # Unknown role - deny access
                return Response(
                    {'error': 'You do not have permission to access reports'},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Apply other filters (available to all roles)
            if status_filter:
                queryset = queryset.filter(status=status_filter)

            if quality_filter:
                queryset = queryset.filter(quality=quality_filter)

            if date_from:
                try:
                    from_date = timezone.datetime.strptime(
                        date_from, '%Y-%m-%d').date()
                    queryset = queryset.filter(created_at__date__gte=from_date)
                except ValueError:
                    pass

            if date_to:
                try:
                    to_date = timezone.datetime.strptime(
                        date_to, '%Y-%m-%d').date()
                    queryset = queryset.filter(created_at__date__lte=to_date)
                except ValueError:
                    pass

            queryset = queryset.order_by('-created_at')

            # Check if user has any products to report
            if not queryset.exists():
                return Response(
                    {'message': 'No products found for the given criteria'},
                    status=status.HTTP_404_NOT_FOUND
                )

            if format_type == 'pdf':
                return self._generate_pdf_report(queryset, user)
            else:
                return self._generate_csv_report(queryset, user)

        except Exception as e:
            logger.error(
                f"Error generating product report for user {request.user.id}: {str(e)}")
            return Response({'error': 'Failed to generate report'}, status=500)

    def _generate_csv_report(self, queryset, user):
        """Generate CSV report"""
        output = io.StringIO()
        writer = csv.writer(output)

        # Header row - adjust based on user role
        if user.role == 'CLIENT':
            # Simplified header for clients (no client info since it's their own)
            writer.writerow([
                'ID',
                'Qualité',
                'Origine',
                'Quantité (Kg)',
                'Prix (DT)',
                'Statut',
                'Paiement',
                'Date Création',
                'Date Fin',
                'Temps Estimation (min)'
            ])
        else:
            # Full header for admin/employee
            writer.writerow([
                'ID',
                'Client',
                'CIN Client',
                'Qualité',
                'Origine',
                'Quantité (Kg)',
                'Prix (DT)',
                'Statut',
                'Paiement',
                'Date Création',
                'Date Fin',
                'Temps Estimation (min)',
                'Créé par'
            ])

        for product in queryset:
            if user.role == 'CLIENT':
                # Simplified row for clients
                writer.writerow([
                    product.id,
                    product.get_quality_display(),
                    product.origine or '',
                    product.quantity,
                    float(product.price) if product.price else 0,
                    product.get_status_display(),
                    product.get_payement_display(),
                    product.created_at.strftime(
                        '%d/%m/%Y %H:%M') if product.created_at else '',
                    product.end_time.strftime(
                        '%d/%m/%Y %H:%M') if product.end_time else '',
                    product.estimation_time
                ])
            else:
                # Full row for admin/employee
                writer.writerow([
                    product.id,
                    product.client.username if product.client else '',
                    product.client.cin if product.client else '',
                    product.get_quality_display(),
                    product.origine or '',
                    product.quantity,
                    float(product.price) if product.price else 0,
                    product.get_status_display(),
                    product.get_payement_display(),
                    product.created_at.strftime(
                        '%d/%m/%Y %H:%M') if product.created_at else '',
                    product.end_time.strftime(
                        '%d/%m/%Y %H:%M') if product.end_time else '',
                    product.estimation_time,
                    product.created_by.username if product.created_by else ''
                ])

        output.seek(0)
        response = HttpResponse(output.getvalue(), content_type='text/csv')

        # Customize filename based on user role
        if user.role == 'CLIENT':
            filename = f'mes_produits_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv'
        else:
            filename = f'rapport_produits_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv'

        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    def _generate_pdf_report(self, queryset, user):
        """Generate PDF report"""
        buffer = io.BytesIO()

        doc = SimpleDocTemplate(
            buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)

        elements = []

        styles = getSampleStyleSheet()
        title_style = styles['Title']
        normal_style = styles['Normal']

        # Customize title based on user role
        if user.role == 'CLIENT':
            title = Paragraph("Mes Produits", title_style)
        else:
            title = Paragraph("Rapport des Produits", title_style)

        elements.append(title)
        elements.append(Spacer(1, 12))

        date_info = Paragraph(
            f"Généré le: {timezone.now().strftime('%d/%m/%Y à %H:%M')}", normal_style)
        elements.append(date_info)
        elements.append(Spacer(1, 12))

        total_products = queryset.count()
        if user.role == 'CLIENT':
            summary = Paragraph(
                f"Total de vos produits: {total_products}", normal_style)
        else:
            summary = Paragraph(
                f"Total des produits: {total_products}", normal_style)
        elements.append(summary)
        elements.append(Spacer(1, 20))

        # Table headers based on user role
        if user.role == 'CLIENT':
            data = [
                ['ID', 'Qualité', 'Quantité', 'Prix', 'Statut', 'Date Création']
            ]
        else:
            data = [
                ['ID', 'Client', 'Qualité', 'Quantité',
                    'Prix', 'Statut', 'Date Création']
            ]

        for product in queryset:
            if user.role == 'CLIENT':
                data.append([
                    str(product.id),
                    product.get_quality_display(),
                    f"{product.quantity} Kg",
                    f"{float(product.price):.2f} DT" if product.price else '0 DT',
                    product.get_status_display(),
                    product.created_at.strftime(
                        '%d/%m/%Y') if product.created_at else ''
                ])
            else:
                data.append([
                    str(product.id),
                    product.client.username[:15] if product.client else '',
                    product.get_quality_display(),
                    f"{product.quantity} Kg",
                    f"{float(product.price):.2f} DT" if product.price else '0 DT',
                    product.get_status_display(),
                    product.created_at.strftime(
                        '%d/%m/%Y') if product.created_at else ''
                ])

        table = Table(data, repeatRows=1)

        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))

        elements.append(table)

        doc.build(elements)

        buffer.seek(0)
        response = HttpResponse(
            buffer.getvalue(), content_type='application/pdf')

        # Customize filename based on user role
        if user.role == 'CLIENT':
            filename = f'mes_produits_{timezone.now().strftime("%Y%m%d_%H%M%S")}.pdf'
        else:
            filename = f'rapport_produits_{timezone.now().strftime("%Y%m%d_%H%M%S")}.pdf'

        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


@method_decorator(csrf_exempt, name='dispatch')
class SingleProductPDFView(View):
    """
    Download PDF report for a specific product by ID
    - Admins and employees can download any product  
    - Clients can only download their own products

    Uses Django View instead of DRF APIView to avoid content negotiation issues
    """

    def dispatch(self, request, *args, **kwargs):
        # Manual authentication check for DRF tokens
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')

        if not auth_header.startswith('Bearer '):
            return JsonResponse({'error': 'Authentication required'}, status=401)

        # Extract token
        token = auth_header.split(' ')[1] if len(
            auth_header.split(' ')) > 1 else None

        if not token:
            return JsonResponse({'error': 'Invalid token format'}, status=401)

        # Authenticate user using DRF token
        from rest_framework.authtoken.models import Token
        from rest_framework_simplejwt.tokens import AccessToken
        from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

        user = None

        # Try JWT token first
        try:
            access_token = AccessToken(token)
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(id=access_token['user_id'])
        except (InvalidToken, TokenError, Exception):
            # Try DRF token authentication
            try:
                token_obj = Token.objects.get(key=token)
                user = token_obj.user
            except Token.DoesNotExist:
                pass

        if not user or not user.is_authenticated:
            return JsonResponse({'error': 'Invalid or expired token'}, status=401)

        # Set user on request
        request.user = user

        return super().dispatch(request, *args, **kwargs)

    def get(self, request, product_id):
        try:
            # Check cache first for PDF
            user_id = request.user.id
            cached_pdf = ProductCacheManager.get_cache('product_pdf', product_id, user_id)
            if cached_pdf:
                logger.info(f"Cache hit for product PDF: {product_id}, user: {user_id}")
                # Return cached PDF data - you might need to adjust this based on your caching strategy
            
            # Debug logging
            logger.info(
                f"PDF download request for product {product_id} by user {request.user.id}")
            logger.info(
                f"User: {request.user.username}, Role: {getattr(request.user, 'role', 'No role')}")

            # Check if user has role attribute
            if not hasattr(request.user, 'role'):
                logger.error(f"User {request.user.id} has no role attribute")
                return JsonResponse({'error': 'User role not found'}, status=403)

            # Get the product with related data
            try:
                product = Product.objects.select_related(
                    'client', 'created_by').get(id=product_id)
                logger.info(
                    f"Product found: {product.id}, Owner: {product.client.username if product.client else 'None'}")
            except Product.DoesNotExist:
                logger.error(f"Product {product_id} not found")
                return JsonResponse({'error': 'Product not found'}, status=404)

            # Apply role-based access control
            user = request.user
            user_role = user.role.upper()  # Ensure uppercase for comparison

            logger.info(f"Checking permissions - User role: {user_role}")

            # Permission logic
            has_permission = False

            if user_role in ['ADMIN', 'EMPLOYEE', 'ACCOUNTANT']:
                # Admin, Employee, and Accountant can access any product
                has_permission = True
                logger.info(
                    f"Access granted: {user_role} can access any product")

            elif user_role == 'CLIENT':
                # Clients can only access their own products
                if product.client and product.client == user:
                    has_permission = True
                    logger.info(
                        f"Access granted: Client can access their own product")
                else:
                    logger.error(
                        f"Access denied: Client {user.id} tried to access product owned by {product.client.id if product.client else 'None'}")

            else:
                logger.error(f"Access denied: Unknown role {user_role}")

            if not has_permission:
                return JsonResponse({
                    'error': 'You do not have permission to access this product'
                }, status=403)

            logger.info(
                f"Permission check passed for user {user.id} to access product {product_id}")

            # Generate PDF
            pdf_data = self._generate_product_pdf(product, user)

            # Cache PDF data for 30 minutes (optional - be careful with binary data caching)
            # ProductCacheManager.set_cache('product_pdf', pdf_data, 1800, product_id, user_id)

            # Create HttpResponse with proper headers
            response = HttpResponse(pdf_data, content_type='application/pdf')

            # Customize filename based on user role
            if user.role.upper() == 'CLIENT':
                filename = f'mon_produit_{product.id}_{timezone.now().strftime("%Y%m%d_%H%M%S")}.pdf'
            else:
                filename = f'produit_{product.id}_{timezone.now().strftime("%Y%m%d_%H%M%S")}.pdf'

            response['Content-Disposition'] = f'attachment; filename="{filename}"'

            # Add CORS headers
            response['Access-Control-Allow-Origin'] = '*'
            response['Access-Control-Allow-Methods'] = 'GET'
            response['Access-Control-Allow-Headers'] = 'Authorization, Content-Type, Accept'
            response['Access-Control-Expose-Headers'] = 'Content-Disposition'

            # Add cache control
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'

            logger.info(
                f"PDF response prepared successfully for product {product.id}")
            return response

        except Exception as e:
            logger.error(f"Error in PDF download: {str(e)}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return JsonResponse({'error': 'Failed to generate PDF'}, status=500)

    def _generate_product_pdf(self, product, user):
        """Generate PDF report for a single product and return binary data"""
        try:
            logger.info(f"Starting PDF generation for product {product.id}")

            buffer = io.BytesIO()
            doc = SimpleDocTemplate(
                buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)

            elements = []
            styles = getSampleStyleSheet()
            title_style = styles['Title']
            heading_style = styles['Heading2']
            normal_style = styles['Normal']

            # Customize title based on user role
            if user.role.upper() == 'CLIENT':
                title = Paragraph(f"Mon Produit #{product.id}", title_style)
            else:
                title = Paragraph(
                    f"Rapport du Produit #{product.id}", title_style)

            elements.append(title)
            elements.append(Spacer(1, 20))

            date_info = Paragraph(
                f"Généré le: {timezone.now().strftime('%d/%m/%Y à %H:%M')}", normal_style)
            elements.append(date_info)
            elements.append(Spacer(1, 30))

            info_title = Paragraph("Informations du Produit", heading_style)
            elements.append(info_title)
            elements.append(Spacer(1, 15))

            # Build product data based on user role
            if user.role.upper() == 'CLIENT':
                # Simplified data for clients
                product_data = [
                    ['Champ', 'Valeur'],
                    ['ID du Produit', str(product.id)],
                    ['Qualité', product.get_quality_display() if hasattr(
                        product, 'get_quality_display') else str(product.quality)],
                    ['Origine', product.origine or 'N/A'],
                    ['Quantité', f"{product.quantity} Kg"],
                    ['Prix Total',
                        f"{float(product.price):.2f} DT" if product.price else '0 DT'],
                    ['Statut', product.get_status_display() if hasattr(
                        product, 'get_status_display') else str(product.status)],
                    ['Date de Création', product.created_at.strftime(
                        '%d/%m/%Y à %H:%M') if product.created_at else 'N/A'],
                    ['Date de Fin', product.end_time.strftime(
                        '%d/%m/%Y à %H:%M') if product.end_time else 'N/A'],
                ]
            else:
                # Full data for admin/employee/accountant
                product_data = [
                    ['Champ', 'Valeur'],
                    ['ID du Produit', str(product.id)],
                    ['Client', product.client.username if product.client else 'N/A'],
                    ['CIN Client', getattr(
                        product.client, 'cin', 'N/A') if product.client else 'N/A'],
                    ['Email Client', product.client.email if product.client else 'N/A'],
                    ['Qualité', product.get_quality_display() if hasattr(
                        product, 'get_quality_display') else str(product.quality)],
                    ['Origine', product.origine or 'N/A'],
                    ['Quantité', f"{product.quantity} Kg"],
                    ['Prix Total',
                        f"{float(product.price):.2f} DT" if product.price else '0 DT'],
                    ['Statut', product.get_status_display() if hasattr(
                        product, 'get_status_display') else str(product.status)],
                    ['Date de Création', product.created_at.strftime(
                        '%d/%m/%Y à %H:%M') if product.created_at else 'N/A'],
                    ['Date de Fin', product.end_time.strftime(
                        '%d/%m/%Y à %H:%M') if product.end_time else 'N/A'],
                    ['Créé par', product.created_by.username if product.created_by else 'N/A'],
                ]

            # Add payment status if available
            if hasattr(product, 'payement') or hasattr(product, 'get_payement_display'):
                payment_status = (product.get_payement_display() if hasattr(product, 'get_payement_display')
                                  else str(getattr(product, 'payement', 'N/A')))

                if user.role.upper() == 'CLIENT':
                    product_data.insert(-2,
                                        ['Statut de Paiement', payment_status])
                else:
                    product_data.insert(-3,
                                        ['Statut de Paiement', payment_status])

            # Add estimation time if available
            if hasattr(product, 'estimation_time') and product.estimation_time:
                estimation_row = ['Temps d\'Estimation',
                                  f"{product.estimation_time} minutes"]
                if user.role.upper() == 'CLIENT':
                    product_data.append(estimation_row)
                else:
                    product_data.insert(-1, estimation_row)

            table = Table(product_data, colWidths=[2.5*inch, 4*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
            ]))

            elements.append(table)

            logger.info(f"Building PDF document for product {product.id}")
            doc.build(elements)
            logger.info(
                f"PDF document built successfully for product {product.id}")

            buffer.seek(0)
            pdf_data = buffer.getvalue()

            logger.info(
                f"PDF generated successfully, size: {len(pdf_data)} bytes")
            return pdf_data

        except Exception as e:
            logger.error(f"Error in _generate_product_pdf: {str(e)}")
            import traceback
            logger.error(f"PDF generation traceback: {traceback.format_exc()}")
            raise


# Alternative: Even simpler function-based view
@csrf_exempt
@require_http_methods(["GET"])
def simple_product_pdf_download(request, product_id):
    """
    Simple function-based view for PDF download
    """
    try:
        # Manual authentication
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('Bearer '):
            return JsonResponse({'error': 'Authentication required'}, status=401)

        token = auth_header.split(' ')[1] if len(
            auth_header.split(' ')) > 1 else None
        if not token:
            return JsonResponse({'error': 'Invalid token'}, status=401)

        # Get user from token (simplified)
        from rest_framework_simplejwt.tokens import AccessToken
        from django.contrib.auth import get_user_model

        try:
            access_token = AccessToken(token)
            User = get_user_model()
            user = User.objects.get(id=access_token['user_id'])
        except Exception:
            return JsonResponse({'error': 'Invalid token'}, status=401)

        # Get product
        try:
            product = Product.objects.select_related(
                'client').get(id=product_id)
        except Product.DoesNotExist:
            return JsonResponse({'error': 'Product not found'}, status=404)

        # Check permissions
        if not hasattr(user, 'role'):
            return JsonResponse({'error': 'No role'}, status=403)

        user_role = user.role.upper()

        if user_role in ['ADMIN', 'EMPLOYEE', 'ACCOUNTANT']:
            # Can access any product
            pass
        elif user_role == 'CLIENT':
            if not product.client or product.client != user:
                return JsonResponse({'error': 'Permission denied'}, status=403)
        else:
            return JsonResponse({'error': 'Invalid role'}, status=403)

        # Generate simple PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)

        elements = []
        styles = getSampleStyleSheet()

        title = Paragraph(f"Product #{product.id} Report", styles['Title'])
        elements.append(title)
        elements.append(Spacer(1, 20))

        content = f"""
        <b>Product ID:</b> {product.id}<br/>
        <b>Quality:</b> {product.quality}<br/>
        <b>Origin:</b> {product.origine or 'N/A'}<br/>
        <b>Quantity:</b> {product.quantity} Kg<br/>
        <b>Price:</b> {float(product.price):.2f} DT<br/>
        <b>Status:</b> {product.status}<br/>
        """

        if user_role != 'CLIENT':
            content += f"<b>Client:</b> {product.client.username if product.client else 'N/A'}<br/>"

        para = Paragraph(content, styles['Normal'])
        elements.append(para)

        doc.build(elements)
        buffer.seek(0)

        response = HttpResponse(
            buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="product_{product.id}.pdf"'

        return response

    except Exception as e:
        logger.error(f"Simple PDF error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


class ProductStatsView(APIView):
    """
    Get product statistics for dashboard
    """
    permission_classes = [permissions.IsAuthenticated, IsAdminOrEmployee]

    def get(self, request):
        try:
            # Check cache first
            cached_stats = ProductCacheManager.get_cache('product_stats')
            if cached_stats:
                logger.info("Cache hit for product statistics")
                return Response(cached_stats)

            total_products = Product.objects.count()
            pending_products = Product.objects.filter(status='pending').count()
            doing_products = Product.objects.filter(status='doing').count()
            done_products = Product.objects.filter(status='done').count()
            canceled_products = Product.objects.filter(
                status='canceled').count()

            unpaid_products = Product.objects.filter(payement='unpaid').count()
            paid_products = Product.objects.filter(payement='paid').count()

            # Quality distribution
            quality_stats = {}
            for choice in Product.QUALITY_CHOICES:
                quality_stats[choice[0]] = Product.objects.filter(
                    quality=choice[0]).count()

            stats_data = {
                'total_products': total_products,
                'status_distribution': {
                    'pending': pending_products,
                    'doing': doing_products,
                    'done': done_products,
                    'canceled': canceled_products
                },
                'payment_distribution': {
                    'unpaid': unpaid_products,
                    'paid': paid_products
                },
                'quality_distribution': quality_stats
            }

            # Cache for 10 minutes
            ProductCacheManager.set_cache('product_stats', stats_data, 600)
            logger.info("Cache set for product statistics")

            return Response(stats_data)
        except Exception as e:
            logger.error(f"Error getting product stats: {str(e)}")
            return Response({'error': 'Failed to get statistics'}, status=500)


class TotalQuantityView(APIView):
    """
    Get total quantity of olives, oil produced, and waste statistics (vendus/non vendus)
    """
    permission_classes = [permissions.IsAuthenticated, IsAdminOrEmployee]

    def get(self, request):
        try:
            # Check cache first - mise à jour de la clé de cache pour inclure les déchets
            cached_quantity = ProductCacheManager.get_cache('total_quantity_with_waste')
            if cached_quantity:
                logger.info("Cache hit for total quantity with waste")
                return Response(cached_quantity)

            # First, let's check if there are any products
            total_products = Product.objects.count()
            logger.info(f"Total products count: {total_products}")

            if total_products == 0:
                empty_result = {
                    'total_quantity': 0,
                    'total_oil_volume': 0,
                    'overall_yield_percentage': 0,
                    'waste_summary': {
                        'total_waste_kg': 0,
                        'waste_vendus_kg': 0,
                        'waste_non_vendus_kg': 0,
                        'waste_vendus_price': 0,
                        'vendus_percentage': 0,
                        'non_vendus_percentage': 0
                    },
                    'message': 'No products found'
                }
                # Cache empty result for shorter time
                ProductCacheManager.set_cache('total_quantity_with_waste', empty_result, 60)
                return Response(empty_result, status=status.HTTP_200_OK)

            # Calculate total quantity of olives across all products
            total_quantity_result = Product.objects.aggregate(
                total=Sum('quantity')
            )
            total_quantity = total_quantity_result['total'] or 0
            logger.info(f"Total quantity: {total_quantity}")

            # Calculate total oil volume - separate queries to avoid type mixing
            # First get products with non-null olive_oil_volume
            total_oil_from_db = Product.objects.filter(
                olive_oil_volume__isnull=False
            ).aggregate(
                total=Sum('olive_oil_volume')
            )['total'] or 0

            # Then calculate for products with null olive_oil_volume
            products_without_oil_volume = Product.objects.filter(
                olive_oil_volume__isnull=True
            )

            manual_oil_calculation = 0
            for product in products_without_oil_volume:
                yield_rate = getattr(Product, 'OLIVE_OIL_YIELD_MAP', {}).get(
                    product.quality, 0.17
                )
                manual_oil_calculation += product.quantity * yield_rate

            total_oil_volume = float(total_oil_from_db) + manual_oil_calculation
            logger.info(f"Total oil volume: {total_oil_volume}")

            # Calculate overall average yield
            overall_yield_percentage = 0
            if total_quantity > 0:
                overall_yield_percentage = (total_oil_volume / float(total_quantity)) * 100

            # NOUVEAU : Calculate waste statistics
            waste_stats = Product.objects.aggregate(
                total_waste=Sum('total_waste_kg'),
                waste_vendus=Sum('waste_vendus_kg'),
                waste_non_vendus=Sum('waste_non_vendus_kg'),
                waste_revenue=Sum('waste_vendus_price')
            )

            total_waste = float(waste_stats['total_waste'] or 0)
            waste_vendus = float(waste_stats['waste_vendus'] or 0)
            waste_non_vendus = float(waste_stats['waste_non_vendus'] or 0)
            waste_revenue = float(waste_stats['waste_revenue'] or 0)

            # Calculate waste percentages
            vendus_percentage = (waste_vendus / total_waste * 100) if total_waste > 0 else 0
            non_vendus_percentage = (waste_non_vendus / total_waste * 100) if total_waste > 0 else 0

            # Get basic breakdown by status (existant)
            quantity_by_status = {}

            status_choices = getattr(Product, 'STATUS_CHOICES', [
                ('pending', 'Pending'),
                ('doing', 'Doing'),
                ('done', 'Done'),
                ('canceled', 'Canceled')
            ])

            for status_choice in status_choices:
                status_key = status_choice[0]
                status_products = Product.objects.filter(status=status_key)

                status_quantity = status_products.aggregate(
                    total=Sum('quantity')
                )['total'] or 0

                # Calculate oil volume for this status - separate queries
                status_oil_from_db = status_products.filter(
                    olive_oil_volume__isnull=False
                ).aggregate(
                    total=Sum('olive_oil_volume')
                )['total'] or 0

                status_manual_oil = 0
                status_products_without_oil = status_products.filter(
                    olive_oil_volume__isnull=True
                )

                for product in status_products_without_oil:
                    yield_rate = getattr(Product, 'OLIVE_OIL_YIELD_MAP', {}).get(
                        product.quality, 0.17
                    )
                    status_manual_oil += product.quantity * yield_rate

                status_oil = float(status_oil_from_db) + status_manual_oil

                # NOUVEAU : Add waste stats by status
                status_waste_stats = status_products.aggregate(
                    total_waste=Sum('total_waste_kg'),
                    vendus=Sum('waste_vendus_kg'),
                    non_vendus=Sum('waste_non_vendus_kg'),
                    revenue=Sum('waste_vendus_price')
                )

                quantity_by_status[status_key] = {
                    'total_quantity': float(status_quantity),
                    'total_oil': float(status_oil),
                    'waste_stats': {
                        'total_waste_kg': float(status_waste_stats['total_waste'] or 0),
                        'waste_vendus_kg': float(status_waste_stats['vendus'] or 0),
                        'waste_non_vendus_kg': float(status_waste_stats['non_vendus'] or 0),
                        'waste_revenue_dt': float(status_waste_stats['revenue'] or 0)
                    }
                }

            # NOUVEAU : Add waste breakdown by quality
            waste_by_quality = {}
            for quality, _ in Product.QUALITY_CHOICES:
                quality_waste = Product.objects.filter(quality=quality).aggregate(
                    total_waste=Sum('total_waste_kg'),
                    vendus=Sum('waste_vendus_kg'),
                    non_vendus=Sum('waste_non_vendus_kg'),
                    revenue=Sum('waste_vendus_price'),
                    product_count=Count('id')
                )
                
                waste_by_quality[quality] = {
                    'product_count': quality_waste['product_count'] or 0,
                    'total_waste_kg': float(quality_waste['total_waste'] or 0),
                    'waste_vendus_kg': float(quality_waste['vendus'] or 0),
                    'waste_non_vendus_kg': float(quality_waste['non_vendus'] or 0),
                    'waste_revenue_dt': float(quality_waste['revenue'] or 0)
                }

            quantity_data = {
                'total_quantity': float(total_quantity),
                'total_oil_volume': float(total_oil_volume),
                'overall_yield_percentage': round(overall_yield_percentage, 2),
                'quantity_by_status': quantity_by_status,
                'total_products': total_products,
                
                # NOUVEAU : Waste summary
                'waste_summary': {
                    'total_waste_kg': round(total_waste, 3),
                    'waste_vendus_kg': round(waste_vendus, 3),
                    'waste_non_vendus_kg': round(waste_non_vendus, 3),
                    'waste_vendus_price_dt': round(waste_revenue, 2),
                    'vendus_percentage': round(vendus_percentage, 2),
                    'non_vendus_percentage': round(non_vendus_percentage, 2),
                    'average_price_per_kg': round(waste_revenue / waste_vendus, 3) if waste_vendus > 0 else 0
                },
                
                # NOUVEAU : Waste breakdown by quality
                'waste_by_quality': waste_by_quality
            }

            # Cache for 15 minutes - update cache key
            ProductCacheManager.set_cache('total_quantity_with_waste', quantity_data, 900)
            logger.info("Cache set for total quantity with waste")

            return Response(quantity_data, status=status.HTTP_200_OK)

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            logger.error(
                f"Error getting total quantity, oil volume, and waste stats: {str(e)}")
            logger.error(f"Full traceback: {error_details}")

            error_response = {
                'error': 'Failed to get total quantity, oil volume, and waste statistics',
                'error_type': type(e).__name__,
                'details': str(e)
            }

            if getattr(settings, 'DEBUG', False):
                error_response['traceback'] = error_details

            return Response(
                error_response,
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class OriginPercentageView(APIView):
    """
    Get percentage distribution of products by origin
    """
    permission_classes = [permissions.IsAuthenticated, IsAdminOrEmployee]

    def get(self, request):
        try:
            # Check cache first
            cached_origins = ProductCacheManager.get_cache('origin_percentages')
            if cached_origins:
                logger.info("Cache hit for origin percentages")
                return Response(cached_origins)

            # Get total count of products (excluding those without origin)
            total_products = Product.objects.exclude(
                Q(origine__isnull=True) | Q(origine__exact='')
            ).count()

            if total_products == 0:
                empty_result = {
                    'message': 'No products with origins found',
                    'total_products': 0,
                    'origin_percentages': []
                }
                # Cache empty result for shorter time
                ProductCacheManager.set_cache('origin_percentages', empty_result, 60)
                return Response(empty_result, status=status.HTTP_200_OK)

            # Get count by origin
            origin_counts = Product.objects.exclude(
                Q(origine__isnull=True) | Q(origine__exact='')
            ).values('origine').annotate(
                count=Count('id'),
                total_quantity=Coalesce(Sum('quantity'), 0)
            ).order_by('-count')

            # Calculate percentages
            origin_percentages = []
            for origin_data in origin_counts:
                percentage = (origin_data['count'] / total_products) * 100
                quantity_percentage = 0

                # Calculate quantity percentage if we have total quantity
                total_quantity = Product.objects.exclude(
                    Q(origine__isnull=True) | Q(origine__exact='')
                ).aggregate(total=Coalesce(Sum('quantity'), 0))['total']

                if total_quantity > 0:
                    quantity_percentage = (
                        origin_data['total_quantity'] / total_quantity) * 100

                origin_percentages.append({
                    'origin': origin_data['origine'],
                    'count': origin_data['count'],
                    'percentage': round(percentage, 2),
                    'total_quantity': origin_data['total_quantity'],
                    'quantity_percentage': round(quantity_percentage, 2)
                })

            origin_data = {
                'total_products_with_origin': total_products,
                'origin_percentages': origin_percentages,
                'summary': {
                    'total_origins': len(origin_percentages),
                    'most_common_origin': origin_percentages[0]['origin'] if origin_percentages else None,
                    'most_common_origin_percentage': origin_percentages[0]['percentage'] if origin_percentages else 0
                }
            }

            # Cache for 15 minutes
            ProductCacheManager.set_cache('origin_percentages', origin_data, 900)
            logger.info("Cache set for origin percentages")

            return Response(origin_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error getting origin percentages: {str(e)}")
            return Response(
                {'error': 'Failed to get origin percentages'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
from django.db.models import Q, Sum, Count, Case, When, DecimalField
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, BasePermission
from django.shortcuts import get_object_or_404
from django.http import HttpResponse, Http404
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import Q, Sum
from .models import Bill, Bilan
from .serializers import BillSerializer, BillUpdateSerializer, BilanSerializer
from users.permissions import IsAdminOrAccountant
from PIL import Image
import img2pdf
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile
import json
import os
from factures.models import Facture
import requests
import logging
from django.core.files.base import ContentFile

# Cache imports
from django.core.cache import cache
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator
from django.views.decorators.vary import vary_on_headers
import hashlib

User = get_user_model()
logger = logging.getLogger(__name__)

# Simple cache manager (inline to avoid import issues)


class SimpleCacheManager:
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
        key = SimpleCacheManager.generate_cache_key(prefix, *args, **kwargs)
        return cache.get(key)

    @staticmethod
    def set_cache(prefix, data, timeout, *args, **kwargs):
        key = SimpleCacheManager.generate_cache_key(prefix, *args, **kwargs)
        return cache.set(key, data, timeout)

    @staticmethod
    def delete_cache(prefix, *args, **kwargs):
        key = SimpleCacheManager.generate_cache_key(prefix, *args, **kwargs)
        return cache.delete(key)


class BillStatisticsView(APIView):
    permission_classes = [IsAuthenticated | IsAdminOrAccountant]

    def get_accessible_bills(self, user):
        if hasattr(user, 'role'):
            user_role = user.role.lower()

            if user_role in ['admin', 'accountant']:
                enterprise_users = User.objects.filter(
                    role__iregex=r'^(admin|accountant)$'
                )
                enterprise_bills = Bill.objects.filter(
                    user__in=enterprise_users)
                return enterprise_bills

        user_bills = Bill.objects.filter(user=user)
        return user_bills

    def get_accessible_factures(self, user):
        """
        Get factures that the user can access based on their role:
        - Regular users: only their own factures
        - Accountants: all factures (shared within enterprise)
        - Admins: all factures (shared within enterprise)
        """
        if hasattr(user, 'role'):
            user_role = user.role.lower()

            if user_role in ['admin', 'accountant']:
                # Admin and accountant can see all factures
                return Facture.objects.all()

        # For regular users, return factures they are clients of
        user_factures = Facture.objects.filter(client=user)
        return user_factures

    def calculate_payment_status_stats(self, factures):
        """
        Calculate payment status statistics for factures
        """
        total_factures = factures.count()

        if total_factures == 0:
            return {
                'paid': {'count': 0, 'percentage': 0.0, 'total_amount': 0.0},
                'unpaid': {'count': 0, 'percentage': 0.0, 'total_amount': 0.0},
                'partial': {'count': 0, 'percentage': 0.0, 'total_amount': 0.0}
            }

        # Count factures by payment status
        payment_stats = factures.aggregate(
            paid_count=Count(Case(When(payment_status='paid', then=1))),
            unpaid_count=Count(Case(When(payment_status='unpaid', then=1))),
            partial_count=Count(Case(When(payment_status='partial', then=1))),

            paid_amount=Sum(Case(When(payment_status='paid', then='final_total'),
                                 default=0, output_field=DecimalField())),
            unpaid_amount=Sum(Case(When(payment_status='unpaid', then='final_total'),
                                   default=0, output_field=DecimalField())),
            partial_amount=Sum(Case(When(payment_status='partial', then='final_total'),
                                    default=0, output_field=DecimalField()))
        )

        # Calculate percentages
        paid_percentage = (
            payment_stats['paid_count'] / total_factures * 100) if total_factures > 0 else 0
        unpaid_percentage = (
            payment_stats['unpaid_count'] / total_factures * 100) if total_factures > 0 else 0
        partial_percentage = (
            payment_stats['partial_count'] / total_factures * 100) if total_factures > 0 else 0

        return {
            'paid': {
                'count': payment_stats['paid_count'],
                'percentage': round(paid_percentage, 2),
                'total_amount': float(payment_stats['paid_amount'] or 0)
            },
            'unpaid': {
                'count': payment_stats['unpaid_count'],
                'percentage': round(unpaid_percentage, 2),
                'total_amount': float(payment_stats['unpaid_amount'] or 0)
            },
            'partial': {
                'count': payment_stats['partial_count'],
                'percentage': round(partial_percentage, 2),
                'total_amount': float(payment_stats['partial_amount'] or 0)
            }
        }

    @method_decorator(vary_on_headers('Authorization'))
    def get(self, request):
        """
        Get separated statistics for expenses and revenue with caching
        """
        # Generate cache key based on user and role
        user_id = request.user.id
        user_role = getattr(request.user, 'role', 'client').lower()

        # Try to get from cache
        cached_stats = SimpleCacheManager.get_cache(
            'bill_stats', user_id, user_role)
        if cached_stats:
            logger.info(f"Cache hit for bill statistics: user {user_id}")
            return Response(cached_stats, status=status.HTTP_200_OK)

        bills = self.get_accessible_bills(request.user)
        factures = self.get_accessible_factures(request.user)

        # Calculate totals separately
        bills_total = bills.aggregate(total=Sum('amount'))['total'] or 0
        factures_total = factures.aggregate(
            total=Sum('final_total'))['total'] or 0

        # Calculate combined total for percentage calculations
        combined_total = bills_total + factures_total

        # Calculate payment status statistics
        payment_status_stats = self.calculate_payment_status_stats(factures)

        # Calculate statistics by category for expenses (bills only)
        expense_category_stats = {}

        # Process bill categories - percentages based on combined total (expenses + revenue)
        for category_code, category_name in Bill.CATEGORY_CHOICES:
            category_bills = bills.filter(category=category_code)
            category_sum = category_bills.aggregate(
                total=Sum('amount'))['total'] or 0
            category_count = category_bills.count()

            # Calculate percentage based on combined total (expenses + revenue)
            percentage = (category_sum / combined_total *
                          100) if combined_total > 0 else 0

            expense_category_stats[category_code] = {
                'name': category_name,
                'total_amount': float(category_sum),
                'count': category_count,
                'percentage': round(percentage, 2),
                'type': 'expense'
            }

        revenue_percentage = (
            factures_total / combined_total * 100) if combined_total > 0 else 0

        revenue_category_stats = {
            'client': {
                'name': 'Client Factures',
                'total_amount': float(factures_total),
                'count': factures.count(),
                # Based on combined total
                'percentage': round(revenue_percentage, 2),
                'type': 'revenue'
            }
        }

        # Combine all categories for the response
        all_category_stats = {
            **expense_category_stats, **revenue_category_stats}

        # Group utilities for summary - percentages based on combined total
        utilities_total = (
            expense_category_stats['water']['total_amount'] +
            expense_category_stats['electricity']['total_amount']
        )
        utilities_count = (
            expense_category_stats['water']['count'] +
            expense_category_stats['electricity']['count']
        )
        utilities_percentage = (
            expense_category_stats['water']['percentage'] +
            expense_category_stats['electricity']['percentage']
        )

        # Calculate net profit/loss
        net_result = factures_total - bills_total
        net_result_type = "profit" if net_result >= 0 else "loss"

        response_data = {
            'total_expenses': float(bills_total),      # Bills only
            'total_revenue': float(factures_total),    # Factures only
            # New field showing total for percentage calculation
            'combined_total': float(combined_total),
            'net_result': float(net_result),           # Revenue - Expenses
            'net_result_type': net_result_type,        # "profit" or "loss"
            'total_bills_count': bills.count(),
            'total_factures_count': factures.count(),
            'total_items_count': bills.count() + factures.count(),

            # Payment status statistics
            'payment_status_stats': payment_status_stats,

            'breakdown_by_type': {
                'expenses': {
                    'total': float(bills_total),
                    'count': bills.count(),
                    'categories': ['water', 'electricity', 'purchase'],
                    'description': 'Operating expenses from bills'
                },
                'revenue': {
                    'total': float(factures_total),
                    'count': factures.count(),
                    'categories': ['client'],
                    'description': 'Income from client factures'
                }
            },
            'category_breakdown': all_category_stats,
            'expense_summary': {
                'utilities': {
                    'name': 'Utilities (Water & Electricity)',
                    'total_amount': utilities_total,
                    'count': utilities_count,
                    'percentage': round(utilities_percentage, 2),
                    'type': 'expense'
                },
                'purchases': {
                    'name': 'Purchases',
                    'total_amount': expense_category_stats['purchase']['total_amount'],
                    'count': expense_category_stats['purchase']['count'],
                    'percentage': expense_category_stats['purchase']['percentage'],
                    'type': 'expense'
                }
            },
            'revenue_summary': {
                'client_factures': {
                    'name': 'Client Factures',
                    'total_amount': revenue_category_stats['client']['total_amount'],
                    'count': revenue_category_stats['client']['count'],
                    'percentage': revenue_category_stats['client']['percentage'],
                    'type': 'revenue'
                }
            }
        }

        # Cache the result for 15 minutes
        SimpleCacheManager.set_cache(
            'bill_stats', response_data, 900, user_id, user_role)
        logger.info(f"Cache set for bill statistics: user {user_id}")

        return Response(response_data, status=status.HTTP_200_OK)


class BillCreateView(APIView):
    permission_classes = [IsAuthenticated | IsAdminOrAccountant]

    def extract_items_from_form_data(self, request_data):
        """
        Extract items from Django formset-style form data
        """
        items = []

        # Check if items are sent as JSON string (existing approach)
        if 'items' in request_data:
            try:
                items_value = request_data['items']
                if isinstance(items_value, str):
                    items = json.loads(items_value)
                elif isinstance(items_value, list):
                    items = items_value
                return items
            except json.JSONDecodeError:
                pass

        # Check for formset-style data (new approach)
        total_forms = request_data.get('items-TOTAL_FORMS')
        if total_forms:
            try:
                total_forms = int(total_forms)

                for i in range(total_forms):
                    title = request_data.get(f'items-{i}-title', '').strip()
                    quantity = request_data.get(f'items-{i}-quantity', '0')
                    unit_price = request_data.get(f'items-{i}-unit_price', '0')

                    if not title:
                        continue

                    try:
                        quantity = float(quantity)
                        unit_price = float(unit_price)

                        item = {
                            'title': title,
                            'quantity': quantity,
                            'unit_price': unit_price
                        }
                        items.append(item)

                    except (ValueError, TypeError) as e:
                        continue

            except (ValueError, TypeError) as e:
                pass

        # Check for alternative formats
        if not items:
            # Try items[0][title] format
            i = 0
            while f'items[{i}][title]' in request_data:
                title = request_data.get(f'items[{i}][title]', '').strip()
                quantity = request_data.get(f'items[{i}][quantity]', '0')
                unit_price = request_data.get(f'items[{i}][unit_price]', '0')

                if title:
                    try:
                        quantity = float(quantity)
                        unit_price = float(unit_price)

                        items.append({
                            'title': title,
                            'quantity': quantity,
                            'unit_price': unit_price
                        })
                    except (ValueError, TypeError):
                        pass
                i += 1

        # Check for item_0_title format
        if not items:
            i = 0
            while f'item_{i}_title' in request_data:
                title = request_data.get(f'item_{i}_title', '').strip()
                quantity = request_data.get(f'item_{i}_quantity', '0')
                unit_price = request_data.get(f'item_{i}_unit_price', '0')

                if title:
                    try:
                        quantity = float(quantity)
                        unit_price = float(unit_price)

                        items.append({
                            'title': title,
                            'quantity': quantity,
                            'unit_price': unit_price
                        })
                    except (ValueError, TypeError):
                        pass
                i += 1

        return items

    def post(self, request):
        if 'original_image' not in request.FILES:
            return Response(
                {"original_image": ["This field is required."]},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Extract items from various possible formats
        items = self.extract_items_from_form_data(request.data)

        # Prepare data for serializer - include both form data and files
        serializer_data = {
            'owner': request.data.get('owner'),
            'category': request.data.get('category'),
            'amount': request.data.get('amount'),
            'payment_date': request.data.get('payment_date'),
            'consumption': request.data.get('consumption'),
            # Include the file
            'original_image': request.FILES['original_image'],
        }

        # Add items if found
        if items:
            serializer_data['items'] = items
        else:
            logger.info("No items found in request data")

        # For purchase bills, ensure items is at least an empty list if not found
        category = serializer_data.get('category')
        if category == 'purchase':
            if 'items' not in serializer_data or not serializer_data['items']:
                serializer_data['items'] = []

        serializer = BillSerializer(
            data=serializer_data,
            context={'request': request}
        )

        if serializer.is_valid():
            img_file = serializer_data['original_image']

            # Convert image to PDF
            try:
                img = Image.open(img_file)

                # Convert image to RGB if necessary (for PDF compatibility)
                if img.mode != 'RGB':
                    img = img.convert('RGB')

                # Create PDF buffer
                pdf_buffer = BytesIO()
                img.save(pdf_buffer, format='PDF', quality=95)
                pdf_buffer.seek(0)

                # Create PDF filename based on original image name
                original_name = img_file.name.split('.')[0]
                pdf_name = f"{original_name}.pdf"

                # Create Django file object from PDF buffer
                pdf_content = ContentFile(pdf_buffer.getvalue())
                pdf_content.name = pdf_name

                # Save the bill (the serializer will handle creating items via the nested relationship)
                bill = serializer.save(user=request.user)

                # Then save the PDF file - this will use the upload_to='bills/pdf/' path from the model
                bill.pdf_file.save(pdf_name, pdf_content, save=True)

                # Clear cache after creating bill
                SimpleCacheManager.delete_cache('bill_stats', request.user.id, getattr(
                    request.user, 'role', 'client').lower())
                SimpleCacheManager.delete_cache('bills_list', request.user.id)

                logger.info(
                    f"Bill created successfully with PDF saved to: {bill.pdf_file.name}")
                logger.info(
                    f"Original image saved to: {bill.original_image.name}")

                return Response(BillSerializer(bill).data, status=status.HTTP_201_CREATED)

            except Exception as e:
                logger.error(f"Error processing image to PDF: {str(e)}")
                return Response(
                    {"error": f"Error processing image: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BillListView(APIView):
    permission_classes = [IsAuthenticated | IsAdminOrAccountant]

    def get_accessible_bills(self, user):
        """
        Get bills that the user can access based on their role:
        - Regular users: only their own bills
        - Accountants: all bills from admin and accountant users (shared within enterprise)
        - Admins: all bills from admin and accountant users (shared within enterprise)
        """
        if hasattr(user, 'role'):
            user_role = user.role.lower()

            if user_role in ['admin', 'accountant']:
                enterprise_users = User.objects.filter(
                    role__iregex=r'^(admin|accountant)$'
                )
                enterprise_bills = Bill.objects.filter(
                    user__in=enterprise_users)
                return enterprise_bills

        user_bills = Bill.objects.filter(user=user)
        return user_bills

    def get(self, request):
        """
        Get all accessible bills for the authenticated user with caching.
        Supports search, filtering by category, pagination, and ordering.
        """
        user_id = request.user.id
        user_role = getattr(request.user, 'role', 'client').lower()

        # Include query parameters in cache key
        query_params = dict(request.query_params)
        query_hash = hashlib.md5(json.dumps(
            query_params, sort_keys=True).encode()).hexdigest()[:8]

        # Try cache first
        cached_result = SimpleCacheManager.get_cache(
            'bills_list', user_id, user_role, query_hash)
        if cached_result:
            logger.info(f"Cache hit for bill list: user {user_id}")
            return Response(cached_result, status=status.HTTP_200_OK)

        bills = self.get_accessible_bills(request.user)

        search_query = request.query_params.get('search', '').strip()
        if search_query:

            bills = bills.filter(
                Q(owner__icontains=search_query) |
                Q(category__icontains=search_query) |
                Q(amount__icontains=search_query)
            )

        category = request.query_params.get('category')
        if category:
            bills = bills.filter(category=category)

        ordering = request.query_params.get('ordering', '-created_at')
        bills = bills.order_by(ordering)

        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 10))

        total_count = bills.count()

        start_index = (page - 1) * page_size
        end_index = start_index + page_size

        paginated_bills = bills[start_index:end_index]

        total_pages = (total_count + page_size -
                       1) // page_size

        serializer = BillSerializer(paginated_bills, many=True)

        response_data = {
            'count': total_count,
            'results': serializer.data,
            'page': page,
            'page_size': page_size,
            'total_pages': total_pages,
            'next': page < total_pages,
            'previous': page > 1
        }

        # Cache for 5 minutes
        SimpleCacheManager.set_cache(
            'bills_list', response_data, 300, user_id, user_role, query_hash)
        logger.info(f"Cache set for bill list: user {user_id}")

        return Response(response_data, status=status.HTTP_200_OK)


class BillDetailView(APIView):
    permission_classes = [IsAuthenticated | IsAdminOrAccountant]

    def get_object(self, bill_id, user):
        """
        Get bill object ensuring user has permission to access it
        """
        bill = get_object_or_404(Bill, id=bill_id)

        if bill.user == user:
            return bill

        if hasattr(user, 'role') and hasattr(bill.user, 'role'):
            user_role = user.role.lower()
            bill_owner_role = bill.user.role.lower()

            if user_role in ['admin', 'accountant'] and bill_owner_role in ['admin', 'accountant']:
                return bill

        raise Http404("Bill not found")

    def get(self, request, bill_id):
        """
        Get a specific bill by ID with caching
        """
        cached_bill = SimpleCacheManager.get_cache(
            'bill_detail', bill_id, request.user.id)
        if cached_bill:
            logger.info(f"Cache hit for bill detail: {bill_id}")
            return Response(cached_bill, status=status.HTTP_200_OK)

        bill = self.get_object(bill_id, request.user)
        serializer = BillSerializer(bill)

        SimpleCacheManager.set_cache(
            'bill_detail', serializer.data, 600, bill_id, request.user.id)
        logger.info(f"Cache set for bill detail: {bill_id}")

        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, bill_id):
        """
        Update a bill (including image fields)
        """
        bill = self.get_object(bill_id, request.user)

        # Use the full BillSerializer instead of BillUpdateSerializer to allow image updates
        serializer = BillSerializer(
            bill,
            data=request.data,
            partial=False,
            context={'request': request}
        )

        if serializer.is_valid():
            updated_bill = serializer.save()

            SimpleCacheManager.delete_cache(
                'bill_detail', bill_id, request.user.id)
            SimpleCacheManager.delete_cache('bill_stats', request.user.id, getattr(
                request.user, 'role', 'client').lower())
            SimpleCacheManager.delete_cache('bills_list', request.user.id)

            return Response(
                BillSerializer(updated_bill).data,
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, bill_id):
        """
        Partially update a bill
        """
        bill = self.get_object(bill_id, request.user)

        # Use the full BillSerializer instead of BillUpdateSerializer to allow image updates
        serializer = BillSerializer(
            bill,
            data=request.data,
            partial=True,
            context={'request': request}
        )

        if serializer.is_valid():
            updated_bill = serializer.save()

            # Clear cache after update
            SimpleCacheManager.delete_cache(
                'bill_detail', bill_id, request.user.id)
            SimpleCacheManager.delete_cache('bill_stats', request.user.id, getattr(
                request.user, 'role', 'client').lower())
            SimpleCacheManager.delete_cache('bills_list', request.user.id)

            return Response(
                BillSerializer(updated_bill).data,
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, bill_id):
        """
        Delete a bill
        """
        bill = self.get_object(bill_id, request.user)

        # Clear cache before delete
        SimpleCacheManager.delete_cache(
            'bill_detail', bill_id, request.user.id)
        SimpleCacheManager.delete_cache('bill_stats', request.user.id, getattr(
            request.user, 'role', 'client').lower())
        SimpleCacheManager.delete_cache('bills_list', request.user.id)

        bill.delete()
        return Response(
            {'message': 'Bill deleted successfully'},
            status=status.HTTP_204_NO_CONTENT
        )

    def post(self, request, bill_id):
        """
        Update only the bill image (separate endpoint for image updates)
        """
        if 'image' not in request.data and 'image' not in request.FILES:
            return Response(
                {'error': 'Image field is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        bill = self.get_object(bill_id, request.user)

        # Only update the image field
        serializer = BillSerializer(
            bill,
            data={'image': request.data.get(
                'image') or request.FILES.get('image')},
            partial=True,
            context={'request': request}
        )

        if serializer.is_valid():
            updated_bill = serializer.save()

            # Clear cache after update
            SimpleCacheManager.delete_cache(
                'bill_detail', bill_id, request.user.id)
            SimpleCacheManager.delete_cache('bill_stats', request.user.id, getattr(
                request.user, 'role', 'client').lower())
            SimpleCacheManager.delete_cache('bills_list', request.user.id)

            return Response(
                BillSerializer(updated_bill).data,
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BillPDFDownloadView(APIView):
    """
    ENHANCED: PDF Download/View endpoint that supports both downloading and viewing
    """
    permission_classes = [IsAuthenticated | IsAdminOrAccountant]

    def get_object(self, bill_id, user):
        """
        Get bill object ensuring user has permission to access it
        """
        bill = get_object_or_404(Bill, id=bill_id)

        # Check if user has permission to access this bill
        if bill.user == user:
            return bill

        # If not the owner, check role-based permissions
        if hasattr(user, 'role') and hasattr(bill.user, 'role'):
            user_role = user.role.lower()
            bill_owner_role = bill.user.role.lower()

            # Admin and accountant can access each other's bills
            if user_role in ['admin', 'accountant'] and bill_owner_role in ['admin', 'accountant']:
                return bill

        # If no permission, raise 404
        raise Http404("Bill not found")

    def get(self, request, bill_id):
        """
        Download or view the PDF file of a specific bill
        Supports both download (attachment) and view (inline) modes
        """
        bill = self.get_object(bill_id, request.user)

        if not bill.pdf_file:
            logger.error(f"PDF file not available for bill {bill_id}")
            return Response(
                {'error': 'PDF file not available for this bill'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check query parameter for display mode
        view_mode = request.query_params.get(
            'view', 'download')  # 'download' or 'inline'

        try:
            logger.info(
                f"Attempting to serve PDF for bill {bill_id}, mode: {view_mode}")

            # Check if using Cloudinary storage
            if hasattr(bill.pdf_file, 'url') and 'cloudinary' in str(bill.pdf_file.url):
                logger.info(f"Using Cloudinary PDF URL: {bill.pdf_file.url}")

                # For Cloudinary files, fetch and serve the content
                try:
                    response_data = requests.get(bill.pdf_file.url, timeout=30)

                    if response_data.status_code == 200:
                        # Validate that we got PDF content
                        content_type = response_data.headers.get(
                            'content-type', '')
                        if 'application/pdf' not in content_type and len(response_data.content) > 0:
                            # Check PDF magic bytes
                            if not response_data.content.startswith(b'%PDF'):
                                logger.warning(
                                    f"Retrieved content doesn't appear to be PDF. Content-Type: {content_type}")

                        response = HttpResponse(
                            response_data.content,
                            content_type='application/pdf'
                        )

                        filename = f"bill_{bill_id}.pdf"

                        if view_mode == 'inline':
                            # For viewing in browser/app
                            response['Content-Disposition'] = f'inline; filename="{filename}"'
                        else:
                            # For downloading
                            response['Content-Disposition'] = f'attachment; filename="{filename}"'

                        # Add headers for better caching and security
                        response['Cache-Control'] = 'private, max-age=3600'
                        response['X-Content-Type-Options'] = 'nosniff'

                        logger.info(
                            f"Successfully served PDF for bill {bill_id}, size: {len(response_data.content)} bytes")
                        return response
                    else:
                        logger.error(
                            f"Failed to fetch PDF from Cloudinary: {response_data.status_code}")
                        return Response(
                            {'error': f'PDF file not accessible from Cloudinary (Status: {response_data.status_code})'},
                            status=status.HTTP_404_NOT_FOUND
                        )

                except requests.RequestException as e:
                    logger.error(
                        f"Request error fetching PDF from Cloudinary: {str(e)}")
                    return Response(
                        {'error': f'Network error accessing PDF: {str(e)}'},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE
                    )

            # For local storage (development)
            else:
                logger.info(f"Using local PDF file: {bill.pdf_file.name}")

                # Get the file path
                file_path = bill.pdf_file.path

                # Check if file exists
                if not os.path.exists(file_path):
                    logger.error(f"PDF file not found on server: {file_path}")
                    return Response(
                        {'error': 'PDF file not found on server'},
                        status=status.HTTP_404_NOT_FOUND
                    )

                # Read the file
                try:
                    with open(file_path, 'rb') as pdf_file:
                        file_content = pdf_file.read()

                    # Validate PDF content
                    if not file_content.startswith(b'%PDF'):
                        logger.warning(
                            f"File doesn't appear to be a valid PDF: {file_path}")

                    response = HttpResponse(
                        file_content,
                        content_type='application/pdf'
                    )

                    filename = os.path.basename(file_path)

                    if view_mode == 'inline':
                        # For viewing in browser/app
                        response['Content-Disposition'] = f'inline; filename="{filename}"'
                    else:
                        # For downloading
                        response['Content-Disposition'] = f'attachment; filename="{filename}"'

                    # Add headers for better caching and security
                    response['Cache-Control'] = 'private, max-age=3600'
                    response['X-Content-Type-Options'] = 'nosniff'

                    logger.info(
                        f"Successfully served local PDF for bill {bill_id}, size: {len(file_content)} bytes")
                    return response

                except IOError as e:
                    logger.error(f"IO error reading PDF file: {str(e)}")
                    return Response(
                        {'error': f'Error reading PDF file: {str(e)}'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )

        except Exception as e:
            logger.error(
                f"Unexpected error serving PDF for bill {bill_id}: {str(e)}")
            return Response(
                {'error': f'Error accessing PDF file: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class BillPDFViewView(APIView):
    """
    NEW: Separate endpoint specifically for viewing PDFs inline (for Flutter app)
    """
    permission_classes = [IsAuthenticated | IsAdminOrAccountant]

    def get_object(self, bill_id, user):
        """
        Get bill object ensuring user has permission to access it
        """
        bill = get_object_or_404(Bill, id=bill_id)

        if bill.user == user:
            return bill

        if hasattr(user, 'role') and hasattr(bill.user, 'role'):
            user_role = user.role.lower()
            bill_owner_role = bill.user.role.lower()

            if user_role in ['admin', 'accountant'] and bill_owner_role in ['admin', 'accountant']:
                return bill

        raise Http404("Bill not found")

    def get(self, request, bill_id):
        """
        View PDF inline - specifically designed for Flutter app PDF viewing
        """
        bill = self.get_object(bill_id, request.user)

        if not bill.pdf_file:
            return Response(
                {'error': 'PDF file not available for this bill'},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            # Check if using Cloudinary storage
            if hasattr(bill.pdf_file, 'url') and 'cloudinary' in str(bill.pdf_file.url):
                response_data = requests.get(bill.pdf_file.url, timeout=30)

                if response_data.status_code == 200:
                    response = HttpResponse(
                        response_data.content,
                        content_type='application/pdf'
                    )
                    response['Content-Disposition'] = f'inline; filename="bill_{bill_id}.pdf"'
                    response['Cache-Control'] = 'private, max-age=3600'
                    # For Flutter web
                    response['Access-Control-Allow-Origin'] = '*'
                    return response
                else:
                    return Response(
                        {'error': 'PDF file not accessible'},
                        status=status.HTTP_404_NOT_FOUND
                    )

            # For local storage
            else:
                file_path = bill.pdf_file.path
                if not os.path.exists(file_path):
                    return Response(
                        {'error': 'PDF file not found'},
                        status=status.HTTP_404_NOT_FOUND
                    )

                with open(file_path, 'rb') as pdf_file:
                    response = HttpResponse(
                        pdf_file.read(),
                        content_type='application/pdf'
                    )
                    response['Content-Disposition'] = f'inline; filename="bill_{bill_id}.pdf"'
                    response['Cache-Control'] = 'private, max-age=3600'
                    # For Flutter web
                    response['Access-Control-Allow-Origin'] = '*'
                    return response

        except Exception as e:
            logger.error(
                f"Error serving PDF view for bill {bill_id}: {str(e)}")
            return Response(
                {'error': f'Error accessing PDF: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class IsExpertComptable(BasePermission):
    """
    Custom permission class to check if user is Expert Comptable
    """

    def has_permission(self, request, view):
        return (request.user and
                request.user.is_authenticated and
                hasattr(request.user, 'role') and
                request.user.role == 'EXPERT_COMPTABLE')


class ExpertComptableBilanListView(APIView):
    """
    View for Expert Comptable to get all bilans
    """
    permission_classes = [IsAuthenticated]

    def has_expert_comptable_access(self, user):
        return (hasattr(user, 'role') and
                user.role == 'EXPERT_COMPTABLE')

    def get(self, request):
        if not self.has_expert_comptable_access(request.user):
            return Response(
                {'error': 'Only Expert Comptable can access bilans'},
                status=status.HTTP_403_FORBIDDEN
            )

        bilans = Bilan.objects.all().order_by('-created_at')
        serializer = BilanSerializer(
            bilans, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class ExpertComptableBilanDetailView(APIView):
    """
    View for Expert Comptable to get bilan by ID
    """
    permission_classes = [IsAuthenticated]

    def has_expert_comptable_access(self, user):
        return (hasattr(user, 'role') and
                user.role == 'EXPERT_COMPTABLE')

    def get_object(self, bilan_id):
        try:
            return Bilan.objects.get(id=bilan_id)
        except Bilan.DoesNotExist:
            return None

    def get(self, request, bilan_id):
        if not self.has_expert_comptable_access(request.user):
            return Response(
                {'error': 'Only Expert Comptable can access bilans'},
                status=status.HTTP_403_FORBIDDEN
            )

        bilan = self.get_object(bilan_id)
        if not bilan:
            return Response(
                {'error': 'Bilan not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = BilanSerializer(bilan, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class ExpertComptableBilanCreateView(APIView):
    """
    View for Expert Comptable to create bilans
    """
    permission_classes = [IsAuthenticated, IsExpertComptable]

    def has_expert_comptable_access(self, user):
        return (hasattr(user, 'role') and
                user.role == 'EXPERT_COMPTABLE')

    def post(self, request):
        if not self.has_expert_comptable_access(request.user):
            return Response(
                {'error': 'Only Expert Comptable can create bilans'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = BilanSerializer(
            data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ExpertComptableBilanUpdateView(APIView):
    """
    View for Expert Comptable to update bilans
    """
    permission_classes = [IsAuthenticated]

    def has_expert_comptable_access(self, user):
        return (hasattr(user, 'role') and
                user.role == 'EXPERT_COMPTABLE')

    def get_object(self, bilan_id):
        try:
            return Bilan.objects.get(id=bilan_id)
        except Bilan.DoesNotExist:
            return None

    def put(self, request, bilan_id):
        if not self.has_expert_comptable_access(request.user):
            return Response(
                {'error': 'Only Expert Comptable can update bilans'},
                status=status.HTTP_403_FORBIDDEN
            )

        bilan = self.get_object(bilan_id)
        if not bilan:
            return Response(
                {'error': 'Bilan not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = BilanSerializer(
            bilan, data=request.data, partial=False, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, bilan_id):
        if not self.has_expert_comptable_access(request.user):
            return Response(
                {'error': 'Only Expert Comptable can update bilans'},
                status=status.HTTP_403_FORBIDDEN
            )

        bilan = self.get_object(bilan_id)
        if not bilan:
            return Response(
                {'error': 'Bilan not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = BilanSerializer(
            bilan, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BilanListCreateView(APIView):
    """
    List all bilans or create a new bilan (only for Expert Comptable)
    """
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated(), IsExpertComptable()]
        return [IsAuthenticated()]

    def has_expert_comptable_access(self, user):
        return (hasattr(user, 'role') and
                user.role == 'EXPERT_COMPTABLE')

    def get(self, request):
        bilans = Bilan.objects.all().order_by('-created_at')
        serializer = BilanSerializer(
            bilans, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        if not self.has_expert_comptable_access(request.user):
            return Response(
                {'error': 'Only Expert Comptable can create bilans'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = BilanSerializer(
            data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BilanDetailView(APIView):
    """
    Retrieve, update or delete a bilan (update/delete only for Expert Comptable)
    """
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.request.method in ['PUT', 'PATCH', 'DELETE']:
            return [IsAuthenticated(), IsExpertComptable()]
        return [IsAuthenticated()]

    def has_expert_comptable_access(self, user):
        return (hasattr(user, 'role') and
                user.role == 'EXPERT_COMPTABLE')

    def get_object(self, bilan_id):
        try:
            return Bilan.objects.get(id=bilan_id)
        except Bilan.DoesNotExist:
            return None

    def get(self, request, bilan_id):
        bilan = self.get_object(bilan_id)
        if not bilan:
            return Response(
                {'error': 'Bilan not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = BilanSerializer(bilan, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, bilan_id):
        if not self.has_expert_comptable_access(request.user):
            return Response(
                {'error': 'Only Expert Comptable can update bilans'},
                status=status.HTTP_403_FORBIDDEN
            )

        bilan = self.get_object(bilan_id)
        if not bilan:
            return Response(
                {'error': 'Bilan not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = BilanSerializer(
            bilan, data=request.data, partial=False, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, bilan_id):
        if not self.has_expert_comptable_access(request.user):
            return Response(
                {'error': 'Only Expert Comptable can update bilans'},
                status=status.HTTP_403_FORBIDDEN
            )

        bilan = self.get_object(bilan_id)
        if not bilan:
            return Response(
                {'error': 'Bilan not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = BilanSerializer(
            bilan, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, bilan_id):
        if not self.has_expert_comptable_access(request.user):
            return Response(
                {'error': 'Only Expert Comptable can delete bilans'},
                status=status.HTTP_403_FORBIDDEN
            )

        bilan = self.get_object(bilan_id)
        if not bilan:
            return Response(
                {'error': 'Bilan not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        bilan.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

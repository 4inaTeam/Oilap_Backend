import logging
from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import Q
import csv
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import inch
from .models import Product
from .serializers import ProductSerializer
from users.permissions import IsEmployee, IsAdmin, IsClient
from users.models import CustomUser
from rest_framework.exceptions import ValidationError
from rest_framework.exceptions import NotFound

logger = logging.getLogger(__name__)


class IsAdminOrEmployee(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role in ['ADMIN', 'EMPLOYEE']


class ProductCreateView(generics.CreateAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrEmployee]


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


class ProductListView(generics.ListAPIView):
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated,
                          IsEmployee | IsAdmin | IsClient]

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'role') and user.role in ['ADMIN', 'EMPLOYEE']:
            return Product.objects.all()
        return Product.objects.filter(client=user)


class ClientProductListView(generics.ListAPIView):
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated, IsClient]

    def get_queryset(self):
        return Product.objects.filter(client=self.request.user)\
            .select_related('client', 'created_by')\
            .order_by('-created_at')


class SearchProductByStatus(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrEmployee]

    def get(self, request, status):
        try:
            products = Product.objects.filter(status=status)
            if not products.exists():
                return Response({"message": "No products found with this status."}, status=404)

            serializer = ProductSerializer(products, many=True)
            return Response(serializer.data)
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


class SingleProductPDFView(APIView):
    """
    Download PDF report for a specific product by ID
    - Admins and employees can view any product
    - Clients can only view their own products
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, product_id):
        try:
            # Get the product with related data
            product = Product.objects.select_related(
                'client', 'created_by', 'facture').get(id=product_id)

            # Apply role-based access control
            user = request.user
            if user.role == 'CLIENT':
                # Clients can only access their own products
                if product.client != user:
                    return Response(
                        {'error': 'You do not have permission to access this product'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            elif user.role not in ['ADMIN', 'EMPLOYEE', 'ACCOUNTANT']:
                # Unknown role - deny access
                return Response(
                    {'error': 'You do not have permission to access product reports'},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Generate PDF
            return self._generate_product_pdf(product, user)

        except Product.DoesNotExist:
            return Response({'error': 'Product not found'}, status=404)
        except Exception as e:
            logger.error(
                f"Error generating product PDF for user {request.user.id}: {str(e)}")
            return Response({'error': 'Failed to generate PDF'}, status=500)

    def _generate_product_pdf(self, product, user):
        """Generate PDF report for a single product"""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)

        elements = []
        styles = getSampleStyleSheet()
        title_style = styles['Title']
        heading_style = styles['Heading2']
        normal_style = styles['Normal']

        # Customize title based on user role
        if user.role == 'CLIENT':
            title = Paragraph(f"Mon Produit #{product.id}", title_style)
        else:
            title = Paragraph(f"Rapport du Produit #{product.id}", title_style)

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
        if user.role == 'CLIENT':
            # Simplified data for clients (no sensitive client info or created_by)
            product_data = [
                ['Champ', 'Valeur'],
                ['ID du Produit', str(product.id)],
                ['Qualité', product.get_quality_display()],
                ['Origine', product.origine or 'N/A'],
                ['Quantité', f"{product.quantity} Kg"],
                ['Prix Unitaire',
                    f"{float(product.price/product.quantity):.2f} DT" if product.price and product.quantity else '0 DT'],
                ['Prix Total',
                    f"{float(product.price):.2f} DT" if product.price else '0 DT'],
                ['Statut', product.get_status_display()],
                ['Statut de Paiement', product.get_payement_display()],
                ['Date de Création', product.created_at.strftime(
                    '%d/%m/%Y à %H:%M') if product.created_at else 'N/A'],
                ['Date de Fin', product.end_time.strftime(
                    '%d/%m/%Y à %H:%M') if product.end_time else 'N/A'],
                ['Temps d\'Estimation', f"{product.estimation_time} minutes"],
            ]
        else:
            # Full data for admin/employee
            product_data = [
                ['Champ', 'Valeur'],
                ['ID du Produit', str(product.id)],
                ['Client', product.client.username if product.client else 'N/A'],
                ['CIN Client', product.client.cin if product.client else 'N/A'],
                ['Email Client', product.client.email if product.client else 'N/A'],
                ['Qualité', product.get_quality_display()],
                ['Origine', product.origine or 'N/A'],
                ['Quantité', f"{product.quantity} Kg"],
                ['Prix Unitaire',
                    f"{float(product.price/product.quantity):.2f} DT" if product.price and product.quantity else '0 DT'],
                ['Prix Total',
                    f"{float(product.price):.2f} DT" if product.price else '0 DT'],
                ['Statut', product.get_status_display()],
                ['Statut de Paiement', product.get_payement_display()],
                ['Date de Création', product.created_at.strftime(
                    '%d/%m/%Y à %H:%M') if product.created_at else 'N/A'],
                ['Date de Fin', product.end_time.strftime(
                    '%d/%m/%Y à %H:%M') if product.end_time else 'N/A'],
                ['Temps d\'Estimation', f"{product.estimation_time} minutes"],
                ['Créé par', product.created_by.username if product.created_by else 'N/A'],
            ]

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

        # Add facture information if available
        # For clients, only show if they own the product (already verified above)
        if product.facture:
            elements.append(Spacer(1, 30))
            facture_title = Paragraph(
                "Informations de Facturation", heading_style)
            elements.append(facture_title)
            elements.append(Spacer(1, 15))

            facture_data = [
                ['Champ', 'Valeur'],
                ['Numéro de Facture', product.facture.facture_number],
                ['Statut de Paiement', product.facture.get_payment_status_display()],
                ['Montant Total Facture',
                    f"{float(product.facture.total_amount):.2f} DT" if product.facture.total_amount else '0 DT'],
                ['TVA', f"{float(product.facture.tva_amount):.2f} DT" if product.facture.tva_amount else '0 DT'],
                ['Montant Final',
                    f"{float(product.facture.final_total):.2f} DT" if product.facture.final_total else '0 DT'],
            ]

            facture_table = Table(
                facture_data, colWidths=[2.5*inch, 4*inch])
            facture_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
            ]))

            elements.append(facture_table)

        doc.build(elements)

        buffer.seek(0)
        response = HttpResponse(
            buffer.getvalue(), content_type='application/pdf')

        # Customize filename based on user role
        if user.role == 'CLIENT':
            filename = f'mon_produit_{product.id}_{timezone.now().strftime("%Y%m%d_%H%M%S")}.pdf'
        else:
            filename = f'produit_{product.id}_{timezone.now().strftime("%Y%m%d_%H%M%S")}.pdf'

        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        return response


class ProductStatsView(APIView):
    """
    Get product statistics for dashboard
    """
    permission_classes = [permissions.IsAuthenticated, IsAdminOrEmployee]

    def get(self, request):
        try:
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

            return Response({
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
            })
        except Exception as e:
            logger.error(f"Error getting product stats: {str(e)}")
            return Response({'error': 'Failed to get statistics'}, status=500)

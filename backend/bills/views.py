# Updated views.py to handle form field items data
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.http import HttpResponse, Http404
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import Q
from .models import Bill
from .serializers import BillSerializer, BillUpdateSerializer
from users.permissions import IsAdminOrAccountant
from PIL import Image
import img2pdf
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile
import json
import os

User = get_user_model()

# Updated BillCreateView with proper file handling


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
                print(f"Processing {total_forms} items from formset")

                for i in range(total_forms):
                    title = request_data.get(f'items-{i}-title', '').strip()
                    quantity = request_data.get(f'items-{i}-quantity', '0')
                    unit_price = request_data.get(f'items-{i}-unit_price', '0')

                    print(
                        f"Item {i}: title='{title}', quantity='{quantity}', unit_price='{unit_price}'")

                    # Skip empty items
                    if not title:
                        print(f"Skipping item {i} - no title")
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
                        print(f"Added item {i}: {item}")

                    except (ValueError, TypeError) as e:
                        print(f"Error parsing item {i}: {e}")
                        continue

            except (ValueError, TypeError) as e:
                print(f"Error processing formset: {e}")
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

        print(f"Extracted {len(items)} items total: {items}")
        return items

    def post(self, request):
        # Debug: Print received data and files
        print("Received data keys:", list(request.data.keys()))
        print("Received files:", list(request.FILES.keys()))
        print("Category:", request.data.get('category'))

        # Check if image file is provided
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
            print(f"Extracted {len(items)} items:", items)
        else:
            print("No items found in request data")

        # For purchase bills, ensure items is at least an empty list if not found
        category = serializer_data.get('category')
        if category == 'purchase':
            if 'items' not in serializer_data or not serializer_data['items']:
                serializer_data['items'] = []
            print(
                f"Final items data for validation: {serializer_data.get('items')}")

        print(f"Data being sent to serializer: {list(serializer_data.keys())}")
        print(f"Original image file: {serializer_data['original_image']}")

        serializer = BillSerializer(
            data=serializer_data,
            context={'request': request}
        )

        if serializer.is_valid():
            img_file = serializer_data['original_image']
            img = Image.open(img_file)

            pdf_buffer = BytesIO()
            img.save(pdf_buffer, format='PDF')
            pdf_buffer.seek(0)

            pdf_name = f"{img_file.name.split('.')[0]}.pdf"
            pdf_file = InMemoryUploadedFile(
                pdf_buffer,
                None,
                pdf_name,
                'application/pdf',
                pdf_buffer.getbuffer().nbytes,
                None
            )

            bill = serializer.save(
                user=request.user,
                pdf_file=pdf_file
            )

            return Response(BillSerializer(bill).data, status=status.HTTP_201_CREATED)

        print("Serializer errors:", serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Keep the rest of the views unchanged


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
        Get all accessible bills for the authenticated user.
        Supports filtering by category and ordering.
        """
        bills = self.get_accessible_bills(request.user)

        category = request.query_params.get('category')
        if category:
            bills = bills.filter(category=category)

        ordering = request.query_params.get('ordering', '-created_at')
        bills = bills.order_by(ordering)

        serializer = BillSerializer(bills, many=True)
        return Response({
            'count': bills.count(),
            'results': serializer.data
        }, status=status.HTTP_200_OK)


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
        Get a specific bill by ID
        """
        bill = self.get_object(bill_id, request.user)
        serializer = BillSerializer(bill)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, bill_id):
        """
        Update a bill (excluding image fields)
        """
        bill = self.get_object(bill_id, request.user)

        serializer = BillUpdateSerializer(
            bill,
            data=request.data,
            partial=False,
            context={'request': request}
        )

        if serializer.is_valid():
            updated_bill = serializer.save()
            return Response(
                BillSerializer(updated_bill).data,
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, bill_id):
        """
        Partially update a bill (excluding image fields)
        """
        bill = self.get_object(bill_id, request.user)

        serializer = BillUpdateSerializer(
            bill,
            data=request.data,
            partial=True,
            context={'request': request}
        )

        if serializer.is_valid():
            updated_bill = serializer.save()
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
        bill.delete()
        return Response(
            {'message': 'Bill deleted successfully'},
            status=status.HTTP_204_NO_CONTENT
        )


class BillPDFDownloadView(APIView):
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
        Download the PDF file of a specific bill
        """
        bill = self.get_object(bill_id, request.user)

        if not bill.pdf_file:
            return Response(
                {'error': 'PDF file not available for this bill'},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            # Get the file path
            file_path = bill.pdf_file.path

            # Check if file exists
            if not os.path.exists(file_path):
                return Response(
                    {'error': 'PDF file not found on server'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Read the file
            with open(file_path, 'rb') as pdf_file:
                response = HttpResponse(
                    pdf_file.read(),
                    content_type='application/pdf'
                )
                response[
                    'Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
                return response

        except Exception as e:
            return Response(
                {'error': f'Error downloading file: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from .models import Bill
from .serializers import BillSerializer, BillUpdateSerializer
from users.permissions import IsAdminOrAccountant
from PIL import Image
import img2pdf
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile
import json


class BillCreateView(APIView):
    permission_classes = [IsAuthenticated | IsAdminOrAccountant]

    def post(self, request):
        data = request.data.copy()
        if 'items' in data:
            try:
                data['items'] = json.loads(data['items'])
            except json.JSONDecodeError:
                return Response(
                    {"items": ["Invalid JSON format"]},
                    status=status.HTTP_400_BAD_REQUEST
                )

        serializer = BillSerializer(
            data=data,
            context={'request': request}
        )

        if serializer.is_valid():
            # Convert image to PDF
            img_file = request.FILES['original_image']
            img = Image.open(img_file)

            # Create PDF in memory
            pdf_buffer = BytesIO()
            img.save(pdf_buffer, format='PDF')
            pdf_buffer.seek(0)

            # Create PDF file object
            pdf_name = f"{img_file.name.split('.')[0]}.pdf"
            pdf_file = InMemoryUploadedFile(
                pdf_buffer,
                None,
                pdf_name,
                'application/pdf',
                pdf_buffer.getbuffer().nbytes,
                None
            )

            # Save bill with PDF
            bill = serializer.save(
                user=request.user,
                pdf_file=pdf_file
            )

            return Response(BillSerializer(bill).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BillListView(APIView):
    permission_classes = [IsAuthenticated | IsAdminOrAccountant]

    def get(self, request):
        """
        Get all bills for the authenticated user.
        Supports filtering by category and ordering.
        """
        bills = Bill.objects.filter(user=request.user)

        # Optional filtering by category
        category = request.query_params.get('category')
        if category:
            bills = bills.filter(category=category)

        # Optional ordering (default: newest first)
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
        Get bill object ensuring it belongs to the authenticated user
        """
        return get_object_or_404(Bill, id=bill_id, user=user)

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

        # Use update serializer that excludes image fields
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

        # Use update serializer that excludes image fields
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

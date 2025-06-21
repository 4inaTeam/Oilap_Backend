from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Bill
from .serializers import BillSerializer
from users.permissions import IsAdminOrAccountant
from PIL import Image
import img2pdf
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile




class BillCreateView(APIView):
    permission_classes = [IsAdminOrAccountant]

    def post(self, request):
        serializer = BillSerializer(
            data=request.data,
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

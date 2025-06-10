from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework import status

import io
from PIL import Image
from .utils import classify_image, extract_fields
from .serializers import InvoiceResultSerializer
from .models import Invoice

class InvoiceUploadAPIView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request):
        f = request.FILES.get('file')
        if not f:
            return Response({'detail': 'No file uploaded.'},
                            status=status.HTTP_400_BAD_REQUEST)
        
        try:
            img = Image.open(f).convert("RGB")
        except Exception:
            return Response({'detail': 'Invalid image.'}, status=status.HTTP_400_BAD_REQUEST)
        
        pdf_bytes_io = io.BytesIO()
        img.save(pdf_bytes_io, format='PDF')
        pdf_bytes_io.seek(0)
        
        category, confidence = classify_image(img)
        pay_date, montant = extract_fields(img)

        invoice = Invoice.objects.create(
            filename=f.name,
            category=category,
            confidence=confidence,
            pay_date=pay_date,
            montant=montant
        )

        try:
            img = Image.open(f)
        except Exception:
            return Response({'detail': 'Invalid image.'},
                            status=status.HTTP_400_BAD_REQUEST)

        category, confidence = classify_image(img)
        pay_date, montant = extract_fields(img)

        data = {
            'filename': f.name,
            'category': category,
            'confidence': confidence,
            'pay_date': pay_date,
            'montant': montant,
        }
        serializer = InvoiceResultSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data)

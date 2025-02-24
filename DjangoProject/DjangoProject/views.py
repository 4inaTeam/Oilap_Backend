from django.core.mail import send_mail
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.urls import reverse

User = get_user_model()

class SendVerificationEmail(APIView):
    def post(self, request):
        user = request.user
        token = user.generate_verification_token()
        verification_url = request.build_absolute_uri(reverse('verify-email', args=[token]))

        send_mail(
            'Verify Your Email',
            f'Click the link to verify your email: {verification_url}',
            'your-email@gmail.com',
            [user.email],
            fail_silently=False,
        )

        return Response({'message': 'Verification email sent'}, status=status.HTTP_200_OK)

class VerifyEmail(APIView):
    def get(self, request, token):
        user = get_object_or_404(User, email_verification_token=token)
        user.email_verified = True
        user.save()
        return Response({'message': 'Email verified successfully'}, status=status.HTTP_200_OK)

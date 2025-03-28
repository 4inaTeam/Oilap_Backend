import stripe
from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from factures.models import Facture
from .models import Payment
from .serializers import PaymentIntentSerializer, PaymentSerializer

stripe.api_key = settings.STRIPE_SECRET_KEY

class CreatePaymentIntentView(generics.CreateAPIView):
    serializer_class = PaymentIntentSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            facture = Facture.objects.get(
                id=serializer.validated_data['facture_id'],
                client__custom_user=request.user
            )
            
            payment_intent = stripe.PaymentIntent.create(
                amount=int(facture.total_amount * 100),
                currency='usd',
                payment_method_types=['card'],
                metadata={
                    'facture_id': facture.id,
                    'user_id': request.user.id
                }
            )
            Payment.objects.create(
                facture=facture,
                stripe_payment_intent=payment_intent.id,
                amount=facture.total_amount,
                currency='USD'
            )
            
            return Response({
                'clientSecret': payment_intent.client_secret
            })
            
        except Facture.DoesNotExist:
            return Response(
                {'error': 'Facture non trouvée'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def confirm_payment(request):
    payment_intent_id = request.data.get('payment_intent_id')
    
    try:
        payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        payment = Payment.objects.get(stripe_payment_intent=payment_intent_id)
        
        if payment_intent.status == 'succeeded':
            payment.status = 'succeeded'
            payment.facture.status = 'paid'
            payment.facture.payment_date = timezone.now()
            payment.facture.save()
            payment.save()
            
            return Response({'status': 'payment_succeeded'})
            
        return Response({'status': payment_intent.status})
    
    except Payment.DoesNotExist:
        return Response(
            {'error': 'Paiement non trouvé'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_400_BAD_REQUEST
        )

@csrf_exempt
@api_view(['POST'])
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')
    
    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        return HttpResponse(status=400)

    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        
        try:
            payment = Payment.objects.get(
                stripe_payment_intent=payment_intent['id']
            )
            payment.status = 'succeeded'
            payment.facture.status = 'paid'
            payment.facture.payment_date = timezone.now()
            payment.facture.save()
            payment.save()
            
            # TODO: Ajouter une notification Firebase ici
            
        except Payment.DoesNotExist:
            pass

    return HttpResponse(status=200)
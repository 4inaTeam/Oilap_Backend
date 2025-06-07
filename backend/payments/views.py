from decimal import Decimal
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.conf import settings
import stripe
from .models import Payment
from factures.models import Facture
from .serializers import PaymentSerializer

stripe.api_key = settings.STRIPE_SECRET_KEY


class PaymentViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['ADMIN', 'EMPLOYEE', 'ACCOUNTANT']:
            return Payment.objects.all()
        else:
            return Payment.objects.filter(facture__client=user)

    @action(detail=False, methods=['post'])
    def create_stripe_payment(self, request):
        """Create Stripe payment for a facture"""
        try:
            facture_id = request.data.get('facture_id')
            facture = Facture.objects.get(id=facture_id)

            # Check if user has permission
            if request.user.role not in ['ADMIN', 'EMPLOYEE', 'ACCOUNTANT'] and facture.client != request.user:
                return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

            # Add minimum amount validation
            min_amount = Decimal('0.50')  # $0.50 minimum for USD
            if facture.final_total < min_amount:
                return Response({
                    'error': f'Amount must be at least ${min_amount}. Current amount: ${facture.final_total}'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Create payment intent with restricted payment methods to avoid redirects
            intent = stripe.PaymentIntent.create(
                amount=int(facture.final_total * 100),  # Convert to cents
                currency='usd',
                # Method 1: Use automatic payment methods but disable redirects
                automatic_payment_methods={
                    'enabled': True,
                    'allow_redirects': 'never'
                },
                metadata={
                    'facture_id': facture.id,
                    'facture_number': facture.facture_number,
                    'client_id': facture.client.id
                }
            )

            # Create payment record
            payment = Payment.objects.create(
                facture=facture,
                amount=facture.final_total,
                payment_method='stripe',
                stripe_payment_intent_id=intent.id,
                status='pending'
            )

            return Response({
                'payment_id': payment.id,
                'client_secret': intent.client_secret,
                'payment_intent_id': intent.id,
                'amount': facture.final_total
            })

        except Facture.DoesNotExist:
            return Response({'error': 'Facture not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def create_stripe_payment_card_only(self, request):
        """Create Stripe payment for a facture - Card payments only (alternative method)"""
        try:
            facture_id = request.data.get('facture_id')
            facture = Facture.objects.get(id=facture_id)

            # Check if user has permission
            if request.user.role not in ['ADMIN', 'EMPLOYEE', 'ACCOUNTANT'] and facture.client != request.user:
                return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

            # Add minimum amount validation
            min_amount = Decimal('0.50')  # $0.50 minimum for USD
            if facture.final_total < min_amount:
                return Response({
                    'error': f'Amount must be at least ${min_amount}. Current amount: ${facture.final_total}'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Method 2: Use only card payment methods (no redirects possible)
            intent = stripe.PaymentIntent.create(
                amount=int(facture.final_total * 100),  # Convert to cents
                currency='usd',
                payment_method_types=['card'],  # Only allow card payments
                metadata={
                    'facture_id': facture.id,
                    'facture_number': facture.facture_number,
                    'client_id': facture.client.id
                }
            )

            # Create payment record
            payment = Payment.objects.create(
                facture=facture,
                amount=facture.final_total,
                payment_method='stripe',
                stripe_payment_intent_id=intent.id,
                status='pending'
            )

            return Response({
                'payment_id': payment.id,
                'client_secret': intent.client_secret,
                'payment_intent_id': intent.id,
                'amount': facture.final_total
            })

        except Facture.DoesNotExist:
            return Response({'error': 'Facture not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def confirm_payment(self, request):
        """Confirm a Stripe payment"""
        try:
            payment_intent_id = request.data.get('payment_intent_id')
            payment_method_id = request.data.get('payment_method_id')

            # Confirm the payment intent
            intent = stripe.PaymentIntent.confirm(
                payment_intent_id,
                payment_method=payment_method_id
            )

            # Update payment record
            try:
                payment = Payment.objects.get(stripe_payment_intent_id=payment_intent_id)
                if intent.status == 'succeeded':
                    payment.status = 'completed'
                    # Update facture status to paid
                    payment.facture.payment_status = 'PAID'
                    payment.facture.save()
                elif intent.status == 'requires_action':
                    payment.status = 'requires_action'
                else:
                    payment.status = 'failed'
                payment.save()
            except Payment.DoesNotExist:
                pass

            return Response({
                'status': intent.status,
                'client_secret': intent.client_secret if intent.status == 'requires_action' else None
            })

        except stripe.error.StripeError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
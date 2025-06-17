# payments/views.py

from decimal import Decimal
import logging

from django.conf import settings
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

import stripe

from .models import Payment
from .serializers import PaymentSerializer
from factures.models import Facture

stripe.api_key = settings.STRIPE_SECRET_KEY
logger = logging.getLogger(__name__)


class PaymentViewSet(viewsets.ModelViewSet):
    """
    ViewSet handling:
    - POST /payments/process_web_payment/
    - POST /payments/process_card_payment/
    - POST /payments/confirm_payment/
    """
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['ADMIN', 'ACCOUNTANT']:
            return Payment.objects.all()
        return Payment.objects.filter(facture__client=user)

    def _check_permission(self, request, facture: Facture):
        role = request.user.role
        if role in ['ADMIN', 'ACCOUNTANT']:
            return True
        # CLIENT can only act on their own facture
        return facture.client == request.user

    @action(
        detail=False,
        methods=['post'],
        url_path='process_web_payment',
        permission_classes=[IsAuthenticated]
    )
    def process_web_payment(self, request):
        """
        Create a Stripe PaymentIntent with card payment methods only.
        """
        try:
            facture_id = request.data.get('facture_id')
            facture = Facture.objects.get(id=facture_id)
        except Facture.DoesNotExist:
            return Response({'error': 'Facture not found'},
                            status=status.HTTP_404_NOT_FOUND)

        if not self._check_permission(request, facture):
            return Response({'error': 'Permission denied'},
                            status=status.HTTP_403_FORBIDDEN)

        if facture.final_total < Decimal('0.50'):
            return Response({
                'error': f'Amount must be at least $0.50. Current: ${facture.final_total}'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Instead of using automatic_payment_methods, specify exactly what you want
            intent = stripe.PaymentIntent.create(
                amount=int(facture.final_total * 100),
                currency='usd',
                payment_method_types=['card'],  # Only allow cards
                # Remove automatic_payment_methods entirely
                metadata={
                    'facture_id': facture.id,
                    'client_id': facture.client.id,
                }
            )

            payment = Payment.objects.create(
                facture=facture,
                amount=facture.final_total,
                payment_method='stripe',
                stripe_payment_intent_id=intent.id,
                status='pending'
            )

            return Response({
                'id': str(payment.id),
                'client_secret': intent.client_secret,
                'payment_intent_id': intent.id,
                'amount': facture.final_total
            }, status=status.HTTP_201_CREATED)

        except stripe.error.StripeError as e:
            logger.error("Stripe error in process_web_payment: %s", e)
            return Response({'error': str(e)},
                            status=status.HTTP_400_BAD_REQUEST)

    @action(
        detail=False,
        methods=['post'],
        url_path='process_card_payment',
        permission_classes=[IsAuthenticated]
    )
    def process_card_payment(self, request):
        """
        Create a Stripe PaymentIntent using test tokens for web/desktop payments.
        """
        try:
            facture_id = request.data.get('facture_id')
            facture = Facture.objects.get(id=facture_id)
        except Facture.DoesNotExist:
            return Response({'error': 'Facture not found'},
                        status=status.HTTP_404_NOT_FOUND)

        if not self._check_permission(request, facture):
            return Response({'error': 'Permission denied'},
                        status=status.HTTP_403_FORBIDDEN)

        if facture.final_total < Decimal('0.50'):
            return Response({
                'error': f'Amount must be at least $0.50. Current: ${facture.final_total}'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Extract card details for validation (frontend validation)
        card_number = request.data.get('card_number', '').replace(' ', '')
        exp_month = request.data.get('exp_month')
        exp_year = request.data.get('exp_year')
        cvc = request.data.get('cvc')
        cardholder_name = request.data.get('cardholder_name')

        if not all([card_number, exp_month, exp_year, cvc]):
            return Response({'error': 'Missing required card details'},
                status=status.HTTP_400_BAD_REQUEST)

        try:
            # Map test card numbers to predefined test payment methods
            test_payment_methods = {
                '4242424242424242': 'pm_card_visa',
                '4000056655665556': 'pm_card_visa_debit',
                '5555555555554444': 'pm_card_mastercard',
                '2223003122003222': 'pm_card_mastercard',
                '4000002500003155': 'pm_card_mastercard_prepaid',
                '378282246310005': 'pm_card_amex',
                '371449635398431': 'pm_card_amex',
                '6011111111111117': 'pm_card_discover',
                '3056930009020004': 'pm_card_diners',
                '30569309025904': 'pm_card_diners',
                '3566002020360505': 'pm_card_jcb',
                '6200000000000005': 'pm_card_unionpay',
            }

            # Use predefined test payment method
            payment_method_id = test_payment_methods.get(
                card_number, 'pm_card_visa')

            logger.info(
                f"Using payment method {payment_method_id} for card {card_number[:4]}****")

            # Create PaymentIntent with specific payment method
            # Don't use automatic_payment_methods when specifying a payment_method
            intent = stripe.PaymentIntent.create(
                amount=int(facture.final_total * 100),
                currency='usd',
                payment_method=payment_method_id,
                confirmation_method='manual',
                confirm=True,
                metadata={
                    'facture_id': facture.id,
                    'client_id': facture.client.id,
                    'cardholder_name': cardholder_name or '',
                }
            )

            payment = Payment.objects.create(
                facture=facture,
                amount=facture.final_total,
                payment_method='stripe',
                stripe_payment_intent_id=intent.id,
                status='pending'
            )

            # Update payment status based on intent status
            if intent.status == 'succeeded':
                payment.status = 'completed'
                facture.payment_status = 'paid'
                facture.save()

                # Mark products as paid
                paid_count = facture.products.filter(
                    payement='unpaid'
                ).update(payement='paid')

                logger.info(
                    f"Payment succeeded for facture {facture.id}. Marked {paid_count} products as paid"
                )
            elif intent.status == 'requires_action':
                payment.status = 'requires_action'
            else:
                payment.status = 'failed'

            payment.save()

            return Response({
                'id': str(payment.id),
                'client_secret': intent.client_secret,
                'payment_intent_id': intent.id,
                'payment_method_id': payment_method_id,
                'amount': facture.final_total,
                'status': intent.status
            }, status=status.HTTP_201_CREATED)

        except stripe.error.CardError as e:
            logger.error("Stripe card error in process_card_payment: %s", e)
            return Response({'error': f'Card error: {e.user_message}'},
                status=status.HTTP_400_BAD_REQUEST)
        except stripe.error.StripeError as e:
            logger.error("Stripe error in process_card_payment: %s", e)
            return Response({'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST)

    @action(
        detail=False,
        methods=['post'],
        url_path='confirm_payment',
        permission_classes=[IsAuthenticated]
    )
    def confirm_payment(self, request):
        """
        Confirm a Stripe PaymentIntent and mark the Facture & its Products as paid.
        For web/desktop, also handles card details creation.
        """
        payment_id = request.data.get('payment_id')
        client_secret = request.data.get('client_secret')
        payment_intent_id = request.data.get('payment_intent_id')
        payment_method_id = request.data.get('payment_method_id')
        
        # Web/desktop card details
        card_number = request.data.get('card_number')
        exp_month = request.data.get('exp_month')
        exp_year = request.data.get('exp_year')
        cvc = request.data.get('cvc')
        cardholder_name = request.data.get('cardholder_name')

        # Try to get payment by ID first, then by payment_intent_id as fallback
        try:
            if payment_id:
                payment = Payment.objects.get(id=payment_id)
                payment_intent_id = payment.stripe_payment_intent_id
            else:
                payment = Payment.objects.get(
                    stripe_payment_intent_id=payment_intent_id
                )
        except Payment.DoesNotExist:
            return Response({'error': 'Payment record not found'},
                            status=status.HTTP_404_NOT_FOUND)

        if not self._check_permission(request, payment.facture):
            return Response({'error': 'Permission denied'},
                            status=status.HTTP_403_FORBIDDEN)

        try:
            # Retrieve the intent to check its current status
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)

            # For web/desktop payments with card details, create payment method
            if card_number and exp_month and exp_year and cvc:
                # Map test card numbers to predefined test payment methods
                test_payment_methods = {
                    '4242424242424242': 'pm_card_visa',
                    '4000056655665556': 'pm_card_visa_debit',
                    '5555555555554444': 'pm_card_mastercard',
                    '2223003122003222': 'pm_card_mastercard',
                    '4000002500003155': 'pm_card_mastercard_prepaid',
                    '378282246310005': 'pm_card_amex',
                    '371449635398431': 'pm_card_amex',
                    '6011111111111117': 'pm_card_discover',
                    '3056930009020004': 'pm_card_diners',
                    '30569309025904': 'pm_card_diners',
                    '3566002020360505': 'pm_card_jcb',
                    '6200000000000005': 'pm_card_unionpay',
                }
                
                payment_method_id = test_payment_methods.get(card_number, 'pm_card_visa')
                logger.info(f"Using payment method {payment_method_id} for card {card_number[:4]}****")

            # If it requires confirmation, try to confirm it
            if intent.status == 'requires_confirmation':
                if payment_method_id:
                    intent = stripe.PaymentIntent.confirm(
                        payment_intent_id,
                        payment_method=payment_method_id
                    )
                else:
                    intent = stripe.PaymentIntent.confirm(payment_intent_id)
            # If it requires payment method, attach one and confirm
            elif intent.status == 'requires_payment_method' and payment_method_id:
                intent = stripe.PaymentIntent.confirm(
                    payment_intent_id,
                    payment_method=payment_method_id
                )
            # If it requires action, we can't auto-confirm it
            elif intent.status == 'requires_action':
                logger.info(
                    f"Payment {payment_intent_id} requires user action")

        except stripe.error.StripeError as e:
            logger.error("Stripe confirm error: %s", e)
            return Response({'error': str(e)},
                            status=status.HTTP_400_BAD_REQUEST)

        # Handle statuses
        if intent.status == 'succeeded':
            payment.status = 'completed'
            facture = payment.facture
            facture.payment_status = 'paid'
            facture.save()

            paid_count = facture.products.filter(
                payement='unpaid'
            ).update(payement='paid')

            logger.info(
                f"Marked {paid_count} products as paid on facture {facture.id}"
            )

        elif intent.status == 'requires_action':
            payment.status = 'requires_action'
        elif intent.status == 'requires_payment_method':
            payment.status = 'failed'
        else:
            payment.status = 'failed'

        payment.save()

        return Response({
            'status': intent.status,
            'client_secret': intent.client_secret
            if intent.status == 'requires_action'
            else None
        }, status=status.HTTP_201_CREATED)
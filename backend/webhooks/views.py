from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.conf import settings
import json
import stripe
import logging

# Import your models
from payments.models import Payment
from factures.models import Facture

# Set up logging
logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY

@csrf_exempt
@require_POST
def stripe_webhook(request):
    """Handle Stripe webhook events"""
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    endpoint_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', None)
    
    if not endpoint_secret:
        logger.error('STRIPE_WEBHOOK_SECRET not configured')
        return HttpResponse('Webhook secret not configured', status=500)

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
        logger.info(f'Received Stripe webhook event: {event["type"]}')
        
    except ValueError as e:
        logger.error(f'Invalid payload: {e}')
        return HttpResponse('Invalid payload', status=400)
    except stripe.error.SignatureVerificationError as e:
        logger.error(f'Invalid signature: {e}')
        return HttpResponse('Invalid signature', status=400)

    # Handle the event
    try:
        if event['type'] == 'payment_intent.succeeded':
            payment_intent = event['data']['object']
            handle_payment_success(payment_intent)
            
        elif event['type'] == 'payment_intent.payment_failed':
            payment_intent = event['data']['object']
            handle_payment_failure(payment_intent)
            
        elif event['type'] == 'payment_intent.canceled':
            payment_intent = event['data']['object']
            handle_payment_canceled(payment_intent)
            
        elif event['type'] == 'payment_intent.requires_action':
            payment_intent = event['data']['object']
            handle_payment_requires_action(payment_intent)
            
        else:
            logger.info(f'Unhandled event type: {event["type"]}')
            
    except Exception as e:
        logger.error(f'Error processing webhook: {str(e)}')
        return HttpResponse('Error processing webhook', status=500)

    return HttpResponse('Success', status=200)


def handle_payment_success(payment_intent):
    """Handle successful payment"""
    payment_intent_id = payment_intent['id']
    
    try:
        payment = Payment.objects.get(
            stripe_payment_intent_id=payment_intent_id
        )
        
        # Update payment status
        payment.status = 'completed'
        payment.save()
        
        # Update facture status
        facture = payment.facture
        facture.payment_status = 'paid'
        facture.save()
        
        # Update all products associated with this facture
        if hasattr(facture, 'products') and facture.products.exists():
            facture.products.all().update(payement='paid', status='done')
            logger.info(f'Updated payment status for {facture.products.count()} products')
        
        logger.info(f'Payment succeeded for facture {facture.facture_number}')
        logger.info(f'Amount: ${payment_intent["amount_received"] / 100}')
        
    except Payment.DoesNotExist:
        logger.warning(f'Payment record not found for intent {payment_intent_id}')
        # Try to create payment record from metadata
        create_payment_from_metadata(payment_intent)
        
    except Exception as e:
        logger.error(f'Error handling payment success: {str(e)}')


def handle_payment_failure(payment_intent):
    """Handle failed payment"""
    payment_intent_id = payment_intent['id']
    
    try:
        payment = Payment.objects.get(
            stripe_payment_intent_id=payment_intent_id
        )
        payment.status = 'failed'
        payment.save()
        
        # Update facture and products status
        facture = payment.facture
        facture.payment_status = 'unpaid'
        facture.save()
        
        # Update all products to unpaid
        if hasattr(facture, 'products') and facture.products.exists():
            facture.products.all().update(payement='unpaid')
            logger.info(f'Updated payment status to unpaid for {facture.products.count()} products')
        
        logger.info(f'Payment failed for facture {facture.facture_number}')
        
    except Payment.DoesNotExist:
        logger.warning(f'Payment record not found for failed intent {payment_intent_id}')
    except Exception as e:
        logger.error(f'Error handling payment failure: {str(e)}')


def handle_payment_canceled(payment_intent):
    """Handle canceled payment"""
    payment_intent_id = payment_intent['id']
    
    try:
        payment = Payment.objects.get(
            stripe_payment_intent_id=payment_intent_id
        )
        payment.status = 'canceled'
        payment.save()
        
        logger.info(f'Payment canceled for facture {payment.facture.facture_number}')
        
    except Payment.DoesNotExist:
        logger.warning(f'Payment record not found for canceled intent {payment_intent_id}')
    except Exception as e:
        logger.error(f'Error handling payment cancelation: {str(e)}')


def handle_payment_requires_action(payment_intent):
    """Handle payment that requires additional action"""
    payment_intent_id = payment_intent['id']
    
    try:
        payment = Payment.objects.get(
            stripe_payment_intent_id=payment_intent_id
        )
        payment.status = 'requires_action'
        payment.save()
        
        logger.info(f'Payment requires action for facture {payment.facture.facture_number}')
        
    except Payment.DoesNotExist:
        logger.warning(f'Payment record not found for intent {payment_intent_id}')
    except Exception as e:
        logger.error(f'Error handling payment requires action: {str(e)}')


def create_payment_from_metadata(payment_intent):
    """Create payment record from Stripe metadata if missing"""
    try:
        facture_id = payment_intent['metadata'].get('facture_id')
        if not facture_id:
            logger.error('No facture_id in payment intent metadata')
            return
            
        facture = Facture.objects.get(id=facture_id)
        
        # Create missing payment record
        payment = Payment.objects.create(
            facture=facture,
            amount=payment_intent['amount_received'] / 100,
            payment_method='stripe',
            stripe_payment_intent_id=payment_intent['id'],
            status='completed' if payment_intent['status'] == 'succeeded' else 'pending'
        )
        
        if payment_intent['status'] == 'succeeded':
            facture.payment_status = 'paid'
            facture.save()
            
            # Update associated products
            if hasattr(facture, 'products') and facture.products.exists():
                facture.products.all().update(payement='paid', status='done')
                logger.info(f'Updated payment status for {facture.products.count()} products')
            
        logger.info(f'Created missing payment record for facture {facture.facture_number}')
        
    except Facture.DoesNotExist:
        logger.error(f'Facture {facture_id} not found')
    except Exception as e:
        logger.error(f'Error creating payment from metadata: {str(e)}')
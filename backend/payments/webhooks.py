import stripe
import json
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Payment

@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META['HTTP_STRIPE_SIGNATURE']
    event = None

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        return HttpResponse(status=400)

    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        handle_payment_succeeded(payment_intent)

    return HttpResponse(status=200)

def handle_payment_succeeded(payment_intent):
    payment = Payment.objects.get(
        stripe_payment_intent=payment_intent['id']
    )
    payment.status = 'succeeded'
    payment.facture.status = 'paid'
    payment.facture.payment_date = timezone.now()
    payment.facture.save()
    payment.save()
    
    # TODO: Send Firebase notification
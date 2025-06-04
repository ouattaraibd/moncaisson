from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, JsonResponse
import stripe
import json
import logging
from django.conf import settings
from location.models import Paiement

logger = logging.getLogger(__name__)
stripe.api_key = settings.STRIPE_API_KEY

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
        logger.error("Payload Stripe invalide")
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        logger.error("Signature Stripe invalide")
        return HttpResponse(status=400)

    # Gestion des événements Stripe
    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        transaction_id = payment_intent['metadata'].get('reservation_id')
        
        try:
            payment = Paiement.objects.get(transaction_id=transaction_id)
            payment.statut = 'REUSSI'
            payment.reservation.statut = 'CONFIRME'
            payment.reponse_api = payment_intent
            payment.save()
            payment.reservation.save()
            logger.info(f"Paiement Stripe réussi: {transaction_id}")
        except Paiement.DoesNotExist:
            logger.error(f"Paiement Stripe introuvable: {transaction_id}")

    elif event['type'] == 'payment_intent.payment_failed':
        payment_intent = event['data']['object']
        transaction_id = payment_intent['metadata'].get('reservation_id')
        logger.warning(f"Paiement Stripe échoué: {transaction_id}")

    return HttpResponse(status=200)
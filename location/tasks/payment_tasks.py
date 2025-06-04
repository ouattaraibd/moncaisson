from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging
from location.models import Paiement
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

@shared_task(bind=True, name='location.tasks.payment_tasks.check_pending_payments')
def check_pending_payments(self):
    """Tâche pour vérifier les paiements en attente"""
    Paiement = self.app.get_model('location', 'Paiement')
    
    payments = Paiement.objects.filter(
        statut='EN_ATTENTE',
        date_creation__lt=timezone.now() - timedelta(minutes=30)
    )
    
    for payment in payments:
        try:
            if payment.methode == 'ORANGE':
                verify_orange_payment(payment)
            elif payment.methode == 'WAVE':
                verify_wave_payment(payment)
            elif payment.methode == 'PAYPAL':
                verify_paypal_payment(payment)
            elif payment.methode == 'STRIPE':
                verify_stripe_payment(payment)
        except Exception as e:
            logger.error(f"Erreur vérification paiement {payment.id}: {str(e)}")

def verify_orange_payment(payment):
    """Vérification spécifique Orange Money"""
    response = requests.post(
        f"{settings.ORANGE_MONEY_API_URL}/verify",
        json={'transaction_id': payment.transaction_id},
        headers={'Authorization': f'Bearer {settings.ORANGE_MONEY_API_KEY}'},
        timeout=5
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get('status') == 'SUCCESS':
            payment.statut = 'REUSSI'
            payment.reservation.statut = 'CONFIRME'
            payment.reponse_api = data
            payment.save()
            payment.reservation.save()

def verify_wave_payment(payment):
    """Vérification spécifique Wave"""
    response = requests.get(
        f"{settings.WAVE_API_URL}/transactions/{payment.transaction_id}",
        headers={'Authorization': f'Bearer {settings.WAVE_API_KEY}'},
        timeout=5
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get('status') == 'completed':
            payment.statut = 'REUSSI'
            payment.reservation.statut = 'CONFIRME'
            payment.reponse_api = data
            payment.save()
            payment.reservation.save()

def verify_paypal_payment(payment):
    """Vérification spécifique PayPal"""
    auth_token = get_paypal_auth_token()
    response = requests.get(
        f"{settings.PAYPAL_API_URL}/v2/checkout/orders/{payment.transaction_id}",
        headers={'Authorization': f'Bearer {auth_token}'},
        timeout=5
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get('status') == 'COMPLETED':
            payment.statut = 'REUSSI'
            payment.reservation.statut = 'CONFIRME'
            payment.reponse_api = data
            payment.save()
            payment.reservation.save()

def verify_stripe_payment(payment):
    """Vérification spécifique Stripe"""
    import stripe
    stripe.api_key = settings.STRIPE_API_KEY
    
    try:
        payment_intent = stripe.PaymentIntent.retrieve(payment.transaction_id)
        if payment_intent.status == 'succeeded':
            payment.statut = 'REUSSI'
            payment.reservation.statut = 'CONFIRME'
            payment.reponse_api = payment_intent
            payment.save()
            payment.reservation.save()
    except stripe.error.StripeError as e:
        logger.error(f"Erreur Stripe: {str(e)}")

def get_paypal_auth_token():
    """Obtient un token d'accès PayPal"""
    response = requests.post(
        f"{settings.PAYPAL_API_URL}/v1/oauth2/token",
        auth=(settings.PAYPAL_CLIENT_ID, settings.PAYPAL_SECRET),
        data={'grant_type': 'client_credentials'},
        headers={'Accept': 'application/json'}
    )
    return response.json().get('access_token')
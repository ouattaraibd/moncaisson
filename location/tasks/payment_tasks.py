from location.models import Paiement
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging
import requests
from django.conf import settings
from django.apps import apps

logger = logging.getLogger(__name__)

@shared_task(
    bind=True,
    name='payment.check_pending',
    autoretry_for=(Exception,),
    retry_backoff=60,
    retry_kwargs={'max_retries': 3},
    queue='payments'
)
def check_pending_payments(self):
    """Tâche pour vérifier les paiements en attente"""
    try:
        Paiement = apps.get_model('location', 'Paiement')
        Reservation = apps.get_model('location', 'Reservation')
        
        payments = Paiement.objects.filter(
            statut='EN_ATTENTE',
            date_creation__lt=timezone.now() - timedelta(minutes=30)
        ).select_related('reservation')
        
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
                continue
        
        return f"{payments.count()} paiements vérifiés"
    except Exception as e:
        logger.error(f"Erreur générale dans check_pending_payments: {str(e)}")
        raise self.retry(exc=e)

def verify_orange_payment(payment):
    """Vérification spécifique Orange Money"""
    response = requests.post(
        f"{settings.ORANGE_MONEY_API_URL}/verify",
        json={'transaction_id': payment.transaction_id},
        headers={'Authorization': f'Bearer {settings.ORANGE_MONEY_API_KEY}'},
        timeout=5
    )
    response.raise_for_status()
    data = response.json()
    
    if data.get('status') == 'SUCCESS':
        update_payment_status(payment, 'REUSSI', data)

def verify_wave_payment(payment):
    """Vérification spécifique Wave"""
    response = requests.get(
        f"{settings.WAVE_API_URL}/transactions/{payment.transaction_id}",
        headers={'Authorization': f'Bearer {settings.WAVE_API_KEY}'},
        timeout=5
    )
    response.raise_for_status()
    data = response.json()
    
    if data.get('status') == 'completed':
        update_payment_status(payment, 'REUSSI', data)

def verify_paypal_payment(payment):
    """Vérification spécifique PayPal"""
    auth_token = get_paypal_auth_token()
    response = requests.get(
        f"{settings.PAYPAL_API_URL}/v2/checkout/orders/{payment.transaction_id}",
        headers={'Authorization': f'Bearer {auth_token}'},
        timeout=5
    )
    response.raise_for_status()
    data = response.json()
    
    if data.get('status') == 'COMPLETED':
        update_payment_status(payment, 'REUSSI', data)

def verify_stripe_payment(payment):
    """Vérification spécifique Stripe"""
    import stripe
    stripe.api_key = settings.STRIPE_API_KEY
    
    payment_intent = stripe.PaymentIntent.retrieve(payment.transaction_id)
    if payment_intent.status == 'succeeded':
        update_payment_status(payment, 'REUSSI', payment_intent)

def get_paypal_auth_token():
    """Obtient un token d'accès PayPal"""
    response = requests.post(
        f"{settings.PAYPAL_API_URL}/v1/oauth2/token",
        auth=(settings.PAYPAL_CLIENT_ID, settings.PAYPAL_SECRET),
        data={'grant_type': 'client_credentials'},
        headers={'Accept': 'application/json'},
        timeout=5
    )
    response.raise_for_status()
    return response.json().get('access_token')

def update_payment_status(payment, status, response_data=None):
    """Met à jour le statut du paiement et de la réservation"""
    payment.statut = status
    payment.reponse_api = response_data or {}
    payment.save()
    
    if payment.reservation:
        payment.reservation.statut = 'CONFIRME'
        payment.reservation.save()

@shared_task(name='payment.dummy_task')
def dummy_task():
    """Tâche de test"""
    return "Tâche de paiement exécutée avec succès"


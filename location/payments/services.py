import stripe
import requests
import json
import time
import logging
from django.conf import settings
from django.urls import reverse
from decimal import Decimal

stripe.api_key = settings.STRIPE_SECRET_KEY
logger = logging.getLogger(__name__)

class PaymentService:
    @staticmethod
    def process_payment(reservation, payment_method, request=None):
        """
        Traite un paiement complet (montant principal + caution)
        """
        try:
            # Calcul des montants
            amount = reservation.montant_total - reservation.caution_paid
            caution = reservation.caution_paid

            # Traitement selon la méthode de paiement
            if payment_method == 'stripe':
                result = PaymentService.process_stripe_payment(
                    reservation=reservation,
                    amount=amount,
                    caution=caution,
                    request=request
                )
            elif payment_method == 'cinetpay':
                result = PaymentService.process_cinetpay_payment(
                    reservation=reservation,
                    request=request
                )
            else:
                raise ValueError(f"Méthode de paiement non supportée: {payment_method}")

            # Mise à jour du statut de la réservation
            if result.get('success'):
                reservation.caution_status = 'held' if caution > 0 else 'not_required'
                reservation.save()

            return result

        except Exception as e:
            logger.error(f"Erreur traitement paiement: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }

    @staticmethod
    def process_stripe_payment(reservation, amount, caution, request=None):
        """
        Traitement spécifique pour Stripe
        """
        try:
            # Paiement principal
            payment_intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),  # en centimes
                currency='xof',
                description=f"Réservation #{reservation.id}",
                metadata={
                    'reservation_id': reservation.id,
                    'payment_type': 'principal',
                    'caution_amount': str(caution)
                }
            )

            # Blocage de la caution si nécessaire
            if caution > 0:
                stripe.PaymentIntent.create(
                    amount=int(caution * 100),
                    currency='xof',
                    description=f"Caution réservation #{reservation.id}",
                    metadata={
                        'reservation_id': reservation.id,
                        'payment_type': 'caution'
                    },
                    capture_method='manual'  # Ne pas capturer immédiatement
                )

            return {
                'success': True,
                'client_secret': payment_intent.client_secret,
                'payment_id': payment_intent.id,
                'requires_action': True
            }

        except stripe.error.StripeError as e:
            logger.error(f"Erreur Stripe: {e.user_message}")
            raise

    @staticmethod
    def process_cinetpay_payment(reservation, request):
        """
        Traitement spécifique pour CinetPay
        """
        try:
            payload = {
                "apikey": settings.CINETPAY_API_KEY,
                "site_id": settings.CINETPAY_SITE_ID,
                "transaction_id": f"RES-{reservation.id}-{int(time.time())}",
                "amount": str(reservation.montant_total),
                "currency": "XOF",
                "description": f"Réservation #{reservation.id} (Caution: {reservation.caution_paid} XOF)",
                "customer_name": request.user.get_full_name(),
                "customer_phone": request.user.phone,
                "customer_email": request.user.email,
                "notify_url": request.build_absolute_uri(reverse('cinetpay_notify')),
                "return_url": request.build_absolute_uri(reverse('payment_confirmation', args=[reservation.id])),
                "metadata": json.dumps({
                    "reservation_id": reservation.id,
                    "caution_amount": str(reservation.caution_paid),
                    "payment_type": "full"
                })
            }

            response = requests.post(
                "https://api.cinetpay.com/v2/payment",
                json=payload,
                timeout=10
            )
            response.raise_for_status()

            return {
                'success': True,
                'payment_url': response.json().get('payment_url'),
                'payment_id': payload['transaction_id']
            }

        except requests.RequestException as e:
            logger.error(f"Erreur CinetPay: {str(e)}")
            raise

    @staticmethod
    def handle_stripe_webhook(payload, sig_header):
        """
        Gère les webhooks Stripe pour les cautions
        """
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )

            if event['type'] == 'payment_intent.succeeded':
                payment_intent = event['data']['object']
                reservation_id = payment_intent['metadata'].get('reservation_id')
                payment_type = payment_intent['metadata'].get('payment_type')

                if payment_type == 'caution':
                    logger.info(f"Caution bloquée pour réservation {reservation_id}")

            return True

        except ValueError as e:
            logger.error(f"Erreur webhook Stripe: {str(e)}")
            return False

    @staticmethod
    def handle_cinetpay_webhook(payload):
        """
        Gère les notifications CinetPay pour les cautions
        """
        try:
            metadata = json.loads(payload.get('metadata', '{}'))
            reservation_id = metadata.get('reservation_id')
            caution_amount = Decimal(metadata.get('caution_amount', 0))

            if caution_amount > 0:
                logger.info(f"Caution bloquée pour réservation {reservation_id}")

            return True

        except json.JSONDecodeError as e:
            logger.error(f"Erreur webhook CinetPay: {str(e)}")
            return False

    @staticmethod
    def release_caution(reservation):
        """
        Libère une caution bloquée
        """
        try:
            if reservation.caution_paid <= 0:
                return {'success': False, 'error': 'Aucune caution à libérer'}

            if reservation.paiement.methode == 'stripe':
                # Remboursement Stripe
                refund = stripe.Refund.create(
                    payment_intent=reservation.paiement.transaction_id,
                    amount=int(reservation.caution_paid * 100)
                )
                reservation.caution_status = 'refunded'

            elif reservation.paiement.methode == 'cinetpay':
                # Remboursement CinetPay
                payload = {
                    "apikey": settings.CINETPAY_API_KEY,
                    "site_id": settings.CINETPAY_SITE_ID,
                    "transaction_id": reservation.paiement.transaction_id,
                    "amount": str(reservation.caution_paid)
                }
                response = requests.post(
                    "https://api.cinetpay.com/v2/refund",
                    json=payload,
                    timeout=10
                )
                response.raise_for_status()
                reservation.caution_status = 'refunded'

            reservation.save()
            return {'success': True}

        except stripe.error.StripeError as e:
            logger.error(f"Erreur remboursement Stripe: {e.user_message}")
            return {'success': False, 'error': str(e)}
        except requests.RequestException as e:
            logger.error(f"Erreur remboursement CinetPay: {str(e)}")
            return {'success': False, 'error': str(e)}
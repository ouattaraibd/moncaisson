from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from location.models import Paiement
import json
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

@csrf_exempt
def paypal_webhook(request):
    if request.method == 'POST':
        try:
            # Vérification avec PayPal
            auth_token = get_paypal_auth_token()
            transmission_id = request.headers.get('Paypal-Transmission-Id')
            timestamp = request.headers.get('Paypal-Transmission-Time')
            cert_url = request.headers.get('Paypal-Cert-Url')
            signature = request.headers.get('Paypal-Transmission-Sig')
            
            verify_data = {
                "auth_algo": "SHA256withRSA",
                "cert_url": cert_url,
                "transmission_id": transmission_id,
                "transmission_sig": signature,
                "transmission_time": timestamp,
                "webhook_id": settings.PAYPAL_WEBHOOK_ID,
                "webhook_event": json.loads(request.body)
            }
            
            response = requests.post(
                f"{settings.PAYPAL_API_URL}/v1/notifications/verify-webhook-signature",
                json=verify_data,
                headers={'Authorization': f'Bearer {auth_token}'},
                timeout=5
            )
            
            if response.json().get('verification_status') != 'SUCCESS':
                raise Exception("Signature PayPal invalide")
            
            data = json.loads(request.body)
            event_type = data.get('event_type')
            resource = data.get('resource', {})
            
            if event_type == 'PAYMENT.CAPTURE.COMPLETED':
                transaction_id = resource.get('custom_id')
                payment = Paiement.objects.get(transaction_id=transaction_id)
                payment.statut = 'REUSSI'
                payment.reservation.statut = 'CONFIRME'
                payment.reponse_api = data
                payment.save()
                payment.reservation.save()
                logger.info(f"Paiement PayPal réussi: {transaction_id}")
            
            return JsonResponse({'status': 'success'})
            
        except Exception as e:
            logger.error(f"Erreur webhook PayPal: {str(e)}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
    return JsonResponse({'status': 'error', 'message': 'Méthode non autorisée'}, status=405)

def get_paypal_auth_token():
    response = requests.post(
        f"{settings.PAYPAL_API_URL}/v1/oauth2/token",
        auth=(settings.PAYPAL_CLIENT_ID, settings.PAYPAL_SECRET),
        data={'grant_type': 'client_credentials'},
        headers={'Accept': 'application/json'}
    )
    return response.json().get('access_token')


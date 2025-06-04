from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from location.models import Paiement, Reservation
import json
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

@csrf_exempt
def orange_webhook(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            transaction_id = data.get('txnid')
            status = data.get('status')
            
            if not transaction_id:
                return JsonResponse({'status': 'error', 'message': 'Transaction ID manquant'}, status=400)
            
            # Vérification avec l'API Orange Money
            verification_url = f"{settings.ORANGE_MONEY_API_URL}/verify"
            response = requests.post(
                verification_url,
                json={'transaction_id': transaction_id},
                headers={'Authorization': f'Bearer {settings.ORANGE_MONEY_API_KEY}'},
                timeout=5
            )
            
            if response.status_code != 200:
                raise Exception("Échec de vérification Orange Money")
            
            verification_data = response.json()
            
            payment = Paiement.objects.get(transaction_id=transaction_id)
            reservation = payment.reservation
            
            if status == 'SUCCESS' and verification_data.get('verified'):
                payment.statut = 'REUSSI'
                reservation.statut = 'CONFIRME'
                logger.info(f"Paiement Orange réussi: {transaction_id}")
            else:
                payment.statut = 'ECHOUE'
                logger.warning(f"Paiement Orange échoué: {transaction_id}")
            
            payment.reponse_api = data
            payment.save()
            reservation.save()
            
            return JsonResponse({'status': 'success'})
            
        except Paiement.DoesNotExist:
            logger.error(f"Paiement Orange introuvable: {transaction_id}")
            return JsonResponse({'status': 'error', 'message': 'Transaction introuvable'}, status=404)
        except Exception as e:
            logger.error(f"Erreur webhook Orange: {str(e)}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Méthode non autorisée'}, status=405)
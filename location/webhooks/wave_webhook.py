from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from location.models import Paiement
import json
import logging
import hmac
import hashlib

logger = logging.getLogger(__name__)

@csrf_exempt
def wave_webhook(request):
    if request.method == 'POST':
        try:
            secret = settings.WAVE_WEBHOOK_SECRET
            signature = request.headers.get('X-Wave-Signature')
            body = request.body
            
            # Vérification de la signature
            digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(digest, signature):
                raise Exception("Signature invalide")
            
            data = json.loads(body)
            transaction_id = data.get('client_reference')
            status = data.get('status')
            
            payment = Paiement.objects.get(transaction_id=transaction_id)
            
            if status == 'completed':
                payment.statut = 'REUSSI'
                payment.reservation.statut = 'CONFIRME'
                logger.info(f"Paiement Wave réussi: {transaction_id}")
            else:
                payment.statut = 'ECHOUE'
                logger.warning(f"Paiement Wave échoué: {transaction_id}")
            
            payment.reponse_api = data
            payment.save()
            payment.reservation.save()
            
            return JsonResponse({'status': 'success'})
            
        except Exception as e:
            logger.error(f"Erreur webhook Wave: {str(e)}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
    return JsonResponse({'status': 'error', 'message': 'Méthode non autorisée'}, status=405)


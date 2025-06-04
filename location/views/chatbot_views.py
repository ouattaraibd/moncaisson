from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.conf import settings
import json
import logging

logger = logging.getLogger(__name__)

@login_required
def chat_interface(request):
    """
    Vue principale pour l'interface du chatbot avec gestion de session utilisateur
    """
    try:
        # Configuration dynamique selon l'environnement
        websocket_protocol = 'wss://' if request.is_secure() else 'ws://'
        websocket_url = f"{websocket_protocol}{request.get_host()}/ws/chatbot/"
        
        context = {
            'websocket_url': websocket_url,
            'page_title': 'Assistant Virtuel de Location',
            'user': request.user,
            'debug_mode': settings.DEBUG,
            'chat_history': get_chat_history(request.user)  # Fonction helper
        }
        
        return render(request, 'location/chatbot/interface.html', context)
        
    except Exception as e:
        logger.error(f"Erreur dans chat_interface: {str(e)}", exc_info=True)
        return render(request, 'location/error.html', {
            'error_message': "Erreur de chargement du chatbot"
        })

@require_http_methods(["POST"])
def chat_api(request):
    """
    API endpoint pour le traitement des messages avec validation complète
    """
    try:
        # Vérification des données
        if not request.body:
            return HttpResponseBadRequest("Requête vide")
            
        data = json.loads(request.body)
        message = data.get('message', '').strip()
        
        if not message:
            return JsonResponse({
                'status': 'error',
                'error': 'Message vide'
            }, status=400)
        
        # Traitement du message (à adapter selon votre logique métier)
        response = process_message(message, request.user)
        
        # Journalisation pour le débogage
        logger.info(f"Chat API - User: {request.user} | Message: {message}")
        
        return JsonResponse({
            'status': 'success',
            'response': response,
            'message_id': generate_message_id(),
            'timestamp': timezone.now().isoformat()
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'error': 'Format JSON invalide'
        }, status=400)
    except Exception as e:
        logger.error(f"Erreur chat API: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'error': 'Erreur interne du serveur'
        }, status=500)

# Fonctions helper
def get_chat_history(user):
    """Récupère l'historique de conversation depuis la base de données"""
    # Implémentez votre logique de récupération d'historique ici
    return []

def process_message(message, user):
    """Logique de traitement des messages du chatbot"""
    # Ajoutez ici votre logique de traitement NLP ou règles métiers
    from .chatbot_logic import generate_response  # Implémentation séparée
    
    return generate_response(message, user)

def generate_message_id():
    """Génère un ID unique pour le message"""
    import uuid
    return str(uuid.uuid4())
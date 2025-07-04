# location/api.py
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from datetime import datetime
from .models import Voiture

def check_disponibilite(request, pk):
    """
    Vérifie la disponibilité d'une voiture pour une période donnée
    URL: /api/voiture/<id>/disponibilite/?date_debut=YYYY-MM-DD&date_fin=YYYY-MM-DD
    """
    voiture = get_object_or_404(Voiture, pk=pk)
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')
    
    # Validation des paramètres
    if not all([date_debut, date_fin]):
        return JsonResponse(
            {'error': 'Les paramètres date_debut et date_fin sont requis'}, 
            status=400
        )
    
    try:
        # Conversion des dates
        date_debut = datetime.strptime(date_debut, '%Y-%m-%d').date()
        date_fin = datetime.strptime(date_fin, '%Y-%m-%d').date()
        
        # Vérification de la période
        if date_fin <= date_debut:
            return JsonResponse(
                {'error': 'La date de fin doit être après la date de début'},
                status=400
            )
        
        # Vérification de la disponibilité
        disponible = voiture.est_disponible_pour_periode(date_debut, date_fin)
        
        return JsonResponse({
            'disponible': disponible,
            'dates': {
                'debut': date_debut.strftime('%Y-%m-%d'),
                'fin': date_fin.strftime('%Y-%m-%d')
            },
            'voiture': {
                'id': voiture.id,
                'nom': f"{voiture.marque} {voiture.modele}"
            }
        })
        
    except ValueError:
        return JsonResponse(
            {'error': 'Format de date invalide. Utilisez YYYY-MM-DD'},
            status=400
        )


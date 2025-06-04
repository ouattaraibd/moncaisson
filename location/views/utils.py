from datetime import date, timedelta
from django.db.models import F, Sum, Q
from django.core.cache import cache
from location.models import Reservation
from django.apps import apps

def calculate_occupancy_rate(user):
    """Calcule le taux d'occupation des véhicules d'un propriétaire (version différée)"""
    # Import différé du modèle
    Reservation = apps.get_model('location', 'Reservation')
    
    cache_key = f'occupancy_rate_{user.id}'
    cached = cache.get(cache_key)
    if cached is not None:  # Plus explicite que if cached
        return cached
    
    total_days = 90
    end_date = date.today()
    start_date = end_date - timedelta(days=total_days)
    
    try:
        occupied_days = Reservation.objects.filter(
            voiture__proprietaire=user,
            statut='confirme',
            date_debut__gte=start_date,
            date_debut__lte=end_date
        ).aggregate(
            total=Sum(F('date_fin') - F('date_debut'))
        )['total'] or timedelta(days=0)
        
        total_possible_days = total_days * user.voitures.count()
        rate = round((occupied_days.days / total_possible_days) * 100, 2) if total_possible_days > 0 else 0
        cache.set(cache_key, rate, 3600)  # Cache pour 1 heure
        return rate
    except Exception as e:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured(f"Erreur de calcul du taux d'occupation: {str(e)}")

def verifier_disponibilite(voiture_id, date_debut, date_fin, exclude_reservation_id=None):
    """Vérifie la disponibilité d'un véhicule (version différée)"""
    # Import différé du modèle
    Reservation = apps.get_model('location', 'Reservation')
    
    try:
        queryset = Reservation.objects.filter(
            voiture_id=voiture_id,
            date_debut__lte=date_fin,
            date_fin__gte=date_debut,
            statut='confirme'
        )
        if exclude_reservation_id:
            queryset = queryset.exclude(id=exclude_reservation_id)
        return not queryset.exists()
    except Exception as e:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured(f"Erreur de vérification de disponibilité: {str(e)}")
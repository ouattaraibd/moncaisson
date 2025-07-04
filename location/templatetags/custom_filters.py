from django import template
from django.conf import settings
import os

register = template.Library()

# Filtre pour filtrer un queryset par statut
@register.filter(name='filter_statut')
def filter_statut(queryset, statut):
    """Filtre un queryset par statut"""
    if queryset is None:
        return queryset.none()
    return queryset.filter(statut=statut)

# Opération mathématique
@register.filter
def subtract(value, arg):
    """Soustrait arg à value avec gestion des valeurs None"""
    try:
        return float(value) - float(arg)
    except (TypeError, ValueError):
        return 0

# Accès aux dictionnaires
@register.filter
def get_item(dictionary, key):
    """Récupère une valeur de dictionnaire avec fallback"""
    if not isinstance(dictionary, dict):
        return ''
    return dictionary.get(key, '')

# Système de confiance
@register.filter
def trust_level(score):
    """Convertit un score numérique en niveau textuel"""
    if score is None:
        return "Non évalué"
    
    try:
        score = float(score)
    except (TypeError, ValueError):
        return "Erreur d'évaluation"

    if score >= 80:
        return "Excellent"
    elif score >= 60:
        return "Bon"
    elif score >= 40:
        return "Moyen"
    else:
        return "À améliorer"

@register.filter
def trust_level_color(score):
    """Retourne une couleur en fonction du score"""
    if score is None:
        return "#cccccc"  # Gris
    
    try:
        score = float(score)
    except (TypeError, ValueError):
        return "#cccccc"

    if score >= 80:
        return "#28a745"  # Vert
    elif score >= 60:
        return "#17a2b8"  # Bleu
    elif score >= 40:
        return "#ffc107"  # Jaune
    else:
        return "#dc3545"  # Rouge

@register.filter
def trust_factor_name(factor):
    """Traduit les codes de facteurs en noms lisibles"""
    if not factor:
        return "Inconnu"
        
    names = {
        'account_age': 'Ancienneté',
        'completion_score': 'Profil complet',
        'reservation_history': 'Historique locations',
        'cancellation_rate': 'Taux annulation',
        'average_rating': 'Note moyenne',
        'dispute_rate': 'Litiges',
        'vehicle_quality': 'Qualité véhicules',
        'response_time': 'Temps de réponse',
        'payment_reliability': 'Fiabilité paiements'
    }
    return names.get(factor, factor.replace('_', ' ').title())

@register.filter
def factor_percentage(value, max_value):
    """Calcule un pourcentage avec limites 0-100"""
    try:
        value = float(value)
        max_value = float(max_value)
        if max_value == 0:
            return 0
        percentage = (value / max_value) * 100
        return min(100, max(0, int(percentage)))
    except (TypeError, ValueError, ZeroDivisionError):
        return 0

@register.filter
def improvement_tips(score):
    """Retourne des conseils personnalisés selon le score"""
    if score is None:
        return "Complétez votre profil pour obtenir des conseils personnalisés"

    try:
        score = float(score)
    except (TypeError, ValueError):
        return "Erreur d'évaluation"

    tips = {
        'high': "Continuez comme ça ! Votre excellent score inspire confiance.",
        'medium': "Complétez votre profil et évitez les annulations pour améliorer votre score.",
        'low': "Ajoutez des documents vérifiés et complétez votre profil pour augmenter votre score."
    }

    if score >= 70:
        return tips['high']
    elif score >= 40:
        return tips['medium']
    else:
        return tips['low']

@register.filter
def trust_level_percentage(score):
    """Calcule le pourcentage d'utilisateurs dans ce niveau"""
    # Implémentez votre logique de calcul ici
    # Exemple simplifié :
    ranges = {
        'Excellent': (80, 100),
        'Bon': (60, 79),
        'Moyen': (40, 59),
        'À améliorer': (0, 39)
    }
    # À remplacer par vos statistiques réelles
    return "25%"  # Valeur factice
    
@register.filter
def user_photo(user):
    if user.photo:
        return user.photo.url
    return os.path.join(settings.STATIC_URL, 'images/default-profile.png')


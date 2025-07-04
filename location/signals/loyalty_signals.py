from django.db.models.signals import post_save
from django.dispatch import receiver
from ..models import Reservation, Evaluation, EvaluationLoueur, Litige
from ..services.trust_service import TrustService
import logging

logger = logging.getLogger(__name__)

@receiver(post_save)
def handle_loyalty_creation(sender, instance, created, **kwargs):
    """Version corrigée"""
    try:
        if not created or sender.__name__ != "User":
            return
            
        from location.models.loyalty_models import LoyaltyProfile
        LoyaltyProfile.objects.create(user=instance)
        
    except Exception as e:
        logger.error(f"Erreur création profil fidélité: {e}")
        
@receiver(post_save, sender=Reservation)
def update_trust_on_reservation(sender, instance, **kwargs):
    """Met à jour le score après une réservation"""
    if instance.statut in ['termine', 'annule']:
        TrustService.update_user_trust_score(instance.client)
        if hasattr(instance.voiture, 'proprietaire'):
            TrustService.update_user_trust_score(instance.voiture.proprietaire)

@receiver(post_save, sender=Evaluation)
def update_trust_on_evaluation(sender, instance, **kwargs):
    """Met à jour le score après une évaluation"""
    TrustService.update_user_trust_score(instance.voiture.proprietaire)

@receiver(post_save, sender=EvaluationLoueur)
def update_trust_on_loueur_evaluation(sender, instance, **kwargs):
    """Met à jour le score après une évaluation de loueur"""
    TrustService.update_user_trust_score(instance.evalue)

@receiver(post_save, sender=Litige)
def update_trust_on_dispute(sender, instance, **kwargs):
    """Met à jour le score après un litige"""
    TrustService.update_user_trust_score(instance.reservation.client)
    TrustService.update_user_trust_score(instance.reservation.voiture.proprietaire)


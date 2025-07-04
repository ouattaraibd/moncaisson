from django.db.models.signals import post_save
from django.dispatch import receiver
import logging

logger = logging.getLogger(__name__)

@receiver(post_save)
def handle_delivery_request(sender, instance, created, **kwargs):
    """Version ultra-sécurisée"""
    try:
        # Vérification différée
        if sender.__name__ != "Reservation":
            return
            
        # Import différé
        from location.models.core_models import Reservation
        if not isinstance(instance, Reservation):
            return
            
        if not created or not getattr(instance, 'avec_livraison', False):
            return
            
        # Import différé
        from django.utils import timezone
        from datetime import timedelta
        from location.models.delivery_models import DeliveryRequest
        
        DeliveryRequest.objects.create(
            reservation=instance,
            status='PENDING',
            delivery_address=getattr(instance, 'adresse_livraison', ''),
            estimated_time=timezone.now() + timedelta(hours=2)
        )
        
    except Exception as e:
        logger.error(f"Erreur création livraison: {str(e)}", exc_info=True)


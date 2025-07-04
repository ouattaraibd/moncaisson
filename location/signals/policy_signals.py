from django.db.models.signals import post_save
from django.dispatch import receiver
import logging

logger = logging.getLogger(__name__)

@receiver(post_save)
def handle_policy_assignment(sender, instance, created, **kwargs):
    """Version corrigée avec imports différés"""
    try:
        if not created or sender.__name__ != "User":
            return
            
        from django.db import transaction
        from location.models.policy_models import Policy, PolicyAcceptance
        
        with transaction.atomic():
            user_policy_type = 'LOUEUR' if instance.user_type == 'LOUEUR' else 'PROPRIETAIRE'
            policy = Policy.objects.get(
                policy_type=user_policy_type,
                is_active=True
            )
            PolicyAcceptance.objects.create(
                user=instance,
                policy=policy,
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
    except Exception as e:
        logger.error(f"Policy assignment failed: {e}", exc_info=True)


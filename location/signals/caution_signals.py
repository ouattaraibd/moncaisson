from django.db.models.signals import post_save
from django.dispatch import receiver
from location.models import Reservation
from django.utils import timezone

@receiver(post_save, sender=Reservation)
def handle_caution(sender, instance, **kwargs):
    if instance.statut == 'termine' and instance.caution_paid > 0:
        # Rembourser la caution si pas de litige
        instance.caution_status = 'refunded'
        instance.save()
        
        # Logique de remboursement via votre système de paiement
        # ... code pour initier le remboursement ...
        
    elif instance.statut == 'annule':
        # Annuler et rembourser la caution
        instance.caution_status = 'refunded'
        instance.save()


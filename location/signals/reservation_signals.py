from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from ..models import Reservation, Paiement
import logging

logger = logging.getLogger(__name__)

def register_signals():
    """Enregistre explicitement tous les signaux"""
    logger.info("Enregistrement des signaux de réservation")
    post_save.connect(notify_proprietaire, sender=Reservation, dispatch_uid="reservation_notification")

@receiver(post_save, sender=Reservation)
def notify_proprietaire(sender, instance, created, **kwargs):
    """Notification pour les nouvelles réservations confirmées"""
    if instance.statut == 'confirme':
        try:
            subject = f"Nouvelle réservation #{instance.id}"
            message = f"""
            Bonjour {instance.voiture.proprietaire.get_full_name()},

            Nouvelle réservation pour votre {instance.voiture.marque} {instance.voiture.modele}:
            - Client: {instance.client.get_full_name()}
            - Période: {instance.date_debut} au {instance.date_fin}
            - Montant: {instance.montant_total} XOF

            Connectez-vous pour plus de détails.
            """
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [instance.voiture.proprietaire.email],
                fail_silently=True
            )
        except Exception as e:
            logger.error(f"Erreur notification propriétaire: {str(e)}", exc_info=True)
            
@receiver(post_save, sender=Reservation)
def notify_proprietaire(sender, instance, created, **kwargs):
    if instance.statut == 'confirme':
        context = {
            'reservation': instance,
            'proprietaire': instance.voiture.proprietaire,
            'site_url': settings.SITE_URL,
            'site_name': settings.SITE_NAME
        }
        
        message = render_to_string('location/emails/nouvelle_reservation.txt', context)
        
        send_mail(
            subject=f"Nouvelle réservation #{instance.id}",
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[instance.voiture.proprietaire.email],
            fail_silently=True
        )
        
@receiver(post_save, sender=Paiement)
def update_reservation_on_payment(sender, instance, created, **kwargs):
    """Met à jour la réservation lorsque le paiement est confirmé"""
    if instance.statut == 'REUSSI':
        reservation = instance.reservation
        reservation.statut = 'confirme'
        reservation.save()
        
        # Envoyer une notification
        send_mail(
            f"Paiement confirmé pour réservation #{reservation.id}",
            f"Votre paiement de {instance.montant} XOF a été confirmé.",
            settings.DEFAULT_FROM_EMAIL,
            [reservation.client.email],
            fail_silently=True
        )
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from location.models.core_models import User, Portefeuille
from django.core.exceptions import ValidationError
from ..models import Transaction

@receiver(post_save, sender=User)
def create_user_portefeuille(sender, instance, created, **kwargs):
    """Crée un portefeuille automatiquement pour tous les utilisateurs"""
    if created:
        Portefeuille.objects.get_or_create(proprietaire=instance)
        
@receiver(pre_save, sender=Transaction)
def verifier_solde_retrait(sender, instance, **kwargs):
    """
    Vérifie que le solde est suffisant avant de valider un retrait
    """
    if instance.pk:  # Si l'instance existe déjà (mise à jour)
        original = Transaction.objects.get(pk=instance.pk)
        
        # Si le statut passe à 'valide' et c'est un retrait
        if (instance.statut == 'valide' and 
            original.statut != 'valide' and 
            instance.type_transaction == 'retrait'):
            
            if instance.portefeuille.solde < abs(instance.montant):
                raise ValidationError(
                    f"Solde insuffisant. Solde actuel: {instance.portefeuille.solde} XOF, "
                    f"Retrait demandé: {abs(instance.montant)} XOF"
                )
                
@receiver(post_save, sender=Transaction)
def update_portefeuille_on_transaction(sender, instance, created, **kwargs):
    """
    Met à jour automatiquement le portefeuille lorsque:
    - Une transaction est validée
    - Le statut change vers 'valide'
    """
    if not created and instance.statut == 'valide':
        portefeuille = instance.portefeuille
        
        # Ne pas traiter si déjà traité (vérification via date_traitement)
        if instance.date_traitement:
            return
            
        try:
            with transaction.atomic():
                # Pour les retraits (montant négatif), vérifier le solde
                if instance.montant < 0 and portefeuille.solde < abs(instance.montant):
                    raise ValueError(f"Solde insuffisant pour le retrait: {portefeuille.solde} < {abs(instance.montant)}")
                
                portefeuille.solde += instance.montant  # + car montant négatif pour retrait
                portefeuille.save()
                
                # Marquer comme traité
                instance.date_traitement = timezone.now()
                instance.save(update_fields=['date_traitement'])
                
        except Exception as e:
            # Annuler la transaction et marquer comme erreur
            instance.statut = 'erreur'
            instance.motif_rejet = str(e)
            instance.save()
            raise  # Pour voir l'erreur dans les logs
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.apps import apps
import logging
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.apps import apps
Message = apps.get_model('location', 'Message')

logger = logging.getLogger(__name__)

def connect_messaging_signals():
    """
    Connecte tous les signaux liés à la messagerie de manière robuste et différée.
    Gère les cas d'erreur et fournit des logs détaillés pour le débogage.
    """
    try:
        # Chargement explicite des modèles avec vérification
        Message = apps.get_model('location.Message')
        User = apps.get_model(settings.AUTH_USER_MODEL)
        Conversation = apps.get_model('location.Conversation')

        # Signal de notification
        @receiver(post_save, sender=Message)
        def handle_message_notification(sender, instance, created, **kwargs):
            """
            Gère les notifications et les métriques pour les nouveaux messages.
            """
            if not created or getattr(instance, '_skip_signal', False):
                return

            try:
                with transaction.atomic():
                    # Mise à jour du timestamp de la conversation
                    Conversation.objects.filter(id=instance.conversation.id).update(
                        updated_at=instance.timestamp
                    )

                    # Envoi asynchrone de la notification
                    try:
                        from location.tasks.messaging_tasks import send_message_notification
                        send_message_notification.delay(instance.id)
                        logger.info(f"Notification programmée pour le message {instance.id}")
                    except ImportError as e:
                        logger.error(f"Erreur d'import du task: {e}")
                    except Exception as e:
                        logger.error(f"Erreur de filement de tâche: {e}")

            except Exception as e:
                logger.error(f"Erreur dans le traitement post-save: {e}", exc_info=True)

        # Signal de validation
        @receiver(pre_save, sender=Message)
        def validate_message_content(sender, instance, **kwargs):
            """
            Valide le contenu et les métadonnées du message.
            """
            if not instance.content or not instance.content.strip():
                logger.warning(f"Message vide bloqué (user: {instance.sender_id})")
                raise ValidationError("Le contenu du message ne peut pas être vide")

            max_length = getattr(settings, 'MESSAGE_MAX_LENGTH', 5000)
            if len(instance.content) > max_length:
                raise ValidationError(
                    f"Message trop long ({len(instance.content)}/{max_length} caractères)"
                )

            if not instance.sender_id or not instance.conversation_id:
                raise ValidationError("Expéditeur ou conversation manquant")

        # Signal de nettoyage
        @receiver(post_delete, sender=Message)
        def cleanup_attachments(sender, instance, **kwargs):
            """
            Nettoie les pièces jointes lorsque le message est supprimé.
            """
            if hasattr(instance, 'attachments'):
                for attachment in instance.attachments.all():
                    try:
                        attachment.file.delete(save=False)
                        attachment.delete()
                    except Exception as e:
                        logger.error(f"Erreur suppression pièce jointe {attachment.id}: {e}")

        logger.info("Signaux de messagerie connectés avec succès")
        return True

    except LookupError as e:
        logger.error("Erreur de recherche de modèle:", exc_info=True)
        logger.error("Modèles nécessaires:")
        logger.error("- location.Message")
        logger.error(f"- {settings.AUTH_USER_MODEL}")
        logger.error("Vérifiez:")
        logger.error("1. L'import dans models/__init__.py")
        logger.error("2. La présence dans INSTALLED_APPS")
        logger.error("3. Les migrations appliquées")
        return False

    except Exception as e:
        logger.critical("Échec critique de la connexion des signaux:", exc_info=True)
        return False


def disconnect_messaging_signals():
    """
    Déconnecte les signaux pour les tests ou le rechargement.
    Utile pendant le développement.
    """
    from django.db.models.signals import post_save, pre_save, post_delete
    
    receivers = [
        (post_save, handle_message_notification),
        (pre_save, validate_message_content),
        (post_delete, cleanup_attachments)
    ]
    
    for signal, receiver_fn in receivers:
        try:
            signal.disconnect(receiver=receiver_fn)
        except Exception as e:
            logger.warning(f"Échec déconnexion signal: {e}")

    logger.info("Signaux de messagerie déconnectés")
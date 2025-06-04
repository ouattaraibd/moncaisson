from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from location.models import Message
import logging

logger = logging.getLogger(__name__)

@shared_task(
    bind=True,
    name='location.tasks.messaging_tasks.send_message_notification',
    autoretry_for=(Exception,),
    retry_backoff=60,
    retry_kwargs={'max_retries': 3}
)
def send_message_notification(self, message_id):
    """
    Tâche Celery pour envoyer des notifications par email lorsqu'un nouveau message est reçu
    avec gestion des erreurs et réessais automatiques.
    """
    try:
        # Import différé des modèles
        Message = self.app.get_model('location', 'Message')
        
        # Récupération optimale du message avec les relations
        message = Message.objects.select_related(
            'conversation',
            'sender'
        ).get(id=message_id)
        
        # Préparation des destinataires (exclure l'expéditeur)
        recipients = message.conversation.participants.exclude(
            id=message.sender.id
        ).only('email', 'username')

        # Contexte pour les templates d'email
        context = {
            'sender_name': message.sender.username,
            'message_preview': message.content[:100],
            'conversation_id': message.conversation.id,
            'site_url': 'https://www.moncaisson.com'  # À adapter
        }

        # Envoi des notifications
        for recipient in recipients:
            try:
                # Préparation de l'email
                email = EmailMultiAlternatives(
                    subject=f"✉ Nouveau message de {message.sender.username}",
                    body=strip_tags(
                        render_to_string('messaging/email_notification.txt', context)
                    ),
                    from_email='notifications@moncaisson.com',
                    to=[recipient.email],
                    reply_to=[message.sender.email]
                )
                
                # Version HTML de l'email
                email.attach_alternative(
                    render_to_string('messaging/email_notification.html', context),
                    "text/html"
                )
                
                # Envoi effectif
                email.send(fail_silently=False)
                logger.info(f"Notification envoyée à {recipient.email} pour le message {message_id}")
                
            except Exception as e:
                logger.error(f"Échec envoi à {recipient.email}: {str(e)}")
                continue

    except Message.DoesNotExist:
        logger.error(f"Message {message_id} introuvable")
    except Exception as e:
        logger.critical(f"Échec critique dans la tâche de notification: {str(e)}")
        raise self.retry(exc=e)  # Réessai automatique selon la configuration
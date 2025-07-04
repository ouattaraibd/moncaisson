from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import logging
from django.apps import apps
from django.conf import settings

logger = logging.getLogger(__name__)

@shared_task(
    bind=True,
    name='messaging.send_notification',
    autoretry_for=(Exception,),
    retry_backoff=60,
    retry_kwargs={'max_retries': 3},
    queue='notifications'
)
def send_message_notification(self, message_id=None):
    """
    Tâche Celery pour envoyer des notifications par email
    avec gestion robuste des erreurs et réessais automatiques.
    """
    try:
        if not message_id:
            logger.warning("Notification envoyée sans message_id")
            return "Aucun message_id fourni"

        Message = apps.get_model('location', 'Message')
        User = apps.get_model('location', 'User')
        
        message = Message.objects.select_related(
            'conversation',
            'sender'
        ).prefetch_related(
            'conversation__participants'
        ).get(id=message_id)
        
        recipients = message.conversation.participants.exclude(
            id=message.sender.id
        ).only('email', 'username')

        context = {
            'sender_name': message.sender.get_full_name() or message.sender.username,
            'message_preview': message.content[:100],
            'conversation_id': message.conversation.id,
            'site_url': getattr(settings, 'SITE_URL', 'https://moncaisson.com')
        }

        for recipient in recipients:
            try:
                send_single_notification(recipient, context)
            except Exception as e:
                logger.error(f"Échec envoi à {recipient.email}: {str(e)}")
                continue
        
        return f"Notifications envoyées pour le message {message_id}"
    except Message.DoesNotExist:
        logger.error(f"Message {message_id} introuvable")
        raise
    except Exception as e:
        logger.critical(f"Erreur critique dans send_message_notification: {str(e)}")
        raise self.retry(exc=e)

def send_single_notification(recipient, context):
    """Envoie une notification individuelle"""
    subject = f"Nouveau message de {context['sender_name']}"
    text_content = render_to_string('messaging/email_notification.txt', context)
    html_content = render_to_string('messaging/email_notification.html', context)
    
    email = EmailMultiAlternatives(
        subject=subject,
        body=strip_tags(text_content),
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@moncaisson.com'),
        to=[recipient.email],
        reply_to=[context.get('reply_to', 'noreply@moncaisson.com')]
    )
    email.attach_alternative(html_content, "text/html")
    email.send(fail_silently=False)
    logger.info(f"Notification envoyée à {recipient.email}")

@shared_task(name='messaging.dummy_task')
def dummy_task():
    """Tâche de test"""
    return "Tâche de messagerie exécutée avec succès"


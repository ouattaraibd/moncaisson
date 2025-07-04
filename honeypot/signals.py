# Dans honeypot/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import BlockedIP
from django.core.mail import mail_admins

@receiver(post_save, sender=BlockedIP)
def notify_admin(sender, instance, created, **kwargs):
    if created:
        mail_admins(
            f"Nouvelle IP bloquée: {instance.ip_address}",
            f"Raison: Trop de tentatives de connexion\nDate: {instance.created_at}"
        )
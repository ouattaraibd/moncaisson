from django.db import models
from django.conf import settings
from datetime import timedelta 
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.utils import timezone

class Policy(models.Model):
    POLICY_TYPES = [
        ('GENERAL', 'Politique Générale'),
        ('LOUEUR', 'Politique Loueur'), 
        ('PROPRIETAIRE', 'Politique Propriétaire')
    ]
    
    title = models.CharField(max_length=200)
    version = models.CharField(max_length=20)
    content = models.TextField()
    policy_type = models.CharField(max_length=20, choices=POLICY_TYPES)
    effective_date = models.DateField(default=timezone.now)  # Date par défaut ajoutée
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Politique"
        verbose_name_plural = "Politiques"
        ordering = ['-effective_date']

    def __str__(self):
        return f"{self.title} (v{self.version})"

@receiver(post_migrate)
def create_default_policies(sender, **kwargs):
    if sender.name == 'location':
        Policy.objects.get_or_create(
            title="Politique Propriétaire",
            policy_type='PROPRIETAIRE',
            is_active=True,
            defaults={
                'content': "Politique par défaut pour les propriétaires",
                'version': '1.0',
                'effective_date': timezone.now().date()  # Date explicite ajoutée
            }
        )
        Policy.objects.get_or_create(
            title="Politique Loueur",
            policy_type='LOUEUR', 
            is_active=True,
            defaults={
                'content': "Politique par défaut pour les loueurs",
                'version': '1.0',
                'effective_date': timezone.now().date()  # Date explicite ajoutée
            }
        )

    class Meta:
        verbose_name = "Politique"
        verbose_name_plural = "Politiques"
        ordering = ['-effective_date']

    def __str__(self):
        return f"{self.title} (v{self.version})"

class PolicyAcceptance(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='policy_acceptances'
    )
    policy = models.ForeignKey(
        Policy,
        on_delete=models.CASCADE,
        related_name='acceptances'
    )
    accepted_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.CharField(max_length=300, blank=True)

    class Meta:
        verbose_name = "Acceptation de politique"
        verbose_name_plural = "Acceptations de politiques"
        unique_together = ('user', 'policy')
        ordering = ['-accepted_at']

    def __str__(self):
        return f"{self.user} a accepté {self.policy}"
        
class MessagingPolicy(models.Model):
    max_attachments_per_message = models.PositiveIntegerField(default=3)
    message_edit_window = models.DurationField(default=timedelta(minutes=15))
    allow_message_forwarding = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Politique de messagerie"
        verbose_name_plural = "Politiques de messagerie"

    def __str__(self):
        return f"Politique de messagerie #{self.id}"
        

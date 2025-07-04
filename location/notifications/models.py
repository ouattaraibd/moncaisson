from django.db import models
from location.models.core_models import User

class Notification(models.Model):
    CATEGORY_CHOICES = [
        ('reservation', 'Réservation'),
        ('payment', 'Paiement'),
        ('system', 'Système'),
        ('message', 'Message'),
        ('other', 'Autre'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications',  # Nom unique et explicite
        verbose_name="Utilisateur"
    )
    message = models.CharField(
        max_length=255,
        verbose_name="Message"
    )
    link = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Lien associé"
    )
    is_read = models.BooleanField(
        default=False,
        verbose_name="Lu"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création"
    )
    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        default='other',
        verbose_name="Catégorie"
    )

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.get_category_display()} - {self.message[:50]}..." 

    def mark_as_read(self):
        """Marque la notification comme lue"""
        if not self.is_read:
            self.is_read = True
            self.save()

    @classmethod
    def create_notification(cls, user, message, category='other', link=''):
        """Méthode utilitaire pour créer des notifications"""
        return cls.objects.create(
            user=user,
            message=message,
            category=category,
            link=link
        )


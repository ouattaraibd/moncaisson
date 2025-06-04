from django.db import models
from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

User = 'location.User'

class Conversation(models.Model):
    participants = models.ManyToManyField(
        User,
        related_name='location_conversations',  # Nom unique
        verbose_name="Participants"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Dernière mise à jour"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Conversation active"
    )
    subject = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Sujet"
    )

    class Meta:
        verbose_name = "Conversation"
        verbose_name_plural = "Conversations"
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['updated_at']),
        ]

    def __str__(self):
        participants = ", ".join([u.username for u in self.participants.all()])
        return f"Conversation entre {participants}"

    def get_unread_count(self, user):
        """Nombre de messages non lus pour un utilisateur"""
        return self.messages.exclude(sender=user).filter(read=False).count()

class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='location_messages',  # Nom unique
        verbose_name="Conversation"
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sent_messages',  # Nom unique
        verbose_name="Expéditeur"
    )
    content = models.TextField(
        max_length=5000,
        verbose_name="Contenu"
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date d'envoi"
    )
    read = models.BooleanField(
        default=False,
        verbose_name="Lu"
    )
    deleted_for = models.ManyToManyField(
        User,
        blank=True,
        related_name='location_deleted_messages',  # Nom unique
        verbose_name="Supprimé pour"
    )

    class Meta:
        verbose_name = "Message"
        verbose_name_plural = "Messages"
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['read']),
            models.Index(fields=['conversation', 'timestamp']),
        ]

    def __str__(self):
        return f"Message de {self.sender} le {self.timestamp}"

    def mark_as_read(self):
        if not self.read:
            self.read = True
            self.save(update_fields=['read'])

class MessageAttachment(models.Model):
    ALLOWED_EXTENSIONS = ['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx']
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='location_attachments',  # Nom unique
        verbose_name="Message"
    )
    file = models.FileField(
        upload_to='messaging/attachments/%Y/%m/%d/',
        validators=[
            FileExtensionValidator(allowed_extensions=ALLOWED_EXTENSIONS)
        ],
        verbose_name="Fichier"
    )
    file_type = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Type de fichier"
    )
    file_size = models.PositiveIntegerField(
        verbose_name="Taille du fichier (bytes)"
    )

    class Meta:
        verbose_name = "Pièce jointe"
        verbose_name_plural = "Pièces jointes"

    def save(self, *args, **kwargs):
        if not self.file_type:
            self.file_type = self.file.name.split('.')[-1].lower()
        self.file_size = self.file.size
        super().save(*args, **kwargs)

    def clean(self):
        if self.file.size > self.MAX_FILE_SIZE:
            raise ValidationError(f"La taille du fichier ne doit pas dépasser {self.MAX_FILE_SIZE/1024/1024}MB")

class ConversationArchive(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='location_archived_conversations',  # Nom unique
        verbose_name="Utilisateur"
    )
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        verbose_name="Conversation"
    )
    archived_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date d'archivage"
    )
    archive_reason = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Raison de l'archivage"
    )

    class Meta:
        verbose_name = "Archive de conversation"
        verbose_name_plural = "Archives de conversations"
        unique_together = ('user', 'conversation')
        ordering = ['-archived_at']
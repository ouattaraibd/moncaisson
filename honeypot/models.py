from django.db import models
from django.utils import timezone

class LoginAttempt(models.Model):
    username = models.CharField(max_length=255)
    password = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField()
    timestamp = models.DateTimeField(default=timezone.now)
    user_agent = models.TextField(blank=True, null=True)
    request_path = models.CharField(max_length=255)

    class Meta:
        verbose_name = "Tentative de connexion (Honeypot)"
        verbose_name_plural = "Tentatives de connexion (Honeypot)"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['ip_address']),
            models.Index(fields=['timestamp']),
        ]

    def __str__(self):
        return f"Tentative de {self.username} depuis {self.ip_address}"
        
class BlockedIP(models.Model):
    ip_address = models.GenericIPAddressField(unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    reason = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "IP bloquée"
        verbose_name_plural = "IPs bloquées"
    
    def __str__(self):
        return f"{self.ip_address} (bloquée le {self.created_at})"
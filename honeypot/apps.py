from django.apps import AppConfig

class HoneypotConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'honeypot'  # Changé de 'moncaisson.honeypot' à 'honeypot'
    verbose_name = "Honeypot Security"
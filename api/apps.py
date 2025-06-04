# api/apps.py
from django.apps import AppConfig

class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'

    def ready(self):
        # Assurez-vous que les modèles sont chargés
        from django.apps import apps
        if apps.ready:
            from . import signals  # Si vous avez des signaux
from django.apps import AppConfig
from django.core.checks import register, Tags, Error
import logging
from pathlib import Path
import importlib
from django.conf import settings
from django.utils.autoreload import autoreload_started
from django.db.models.signals import post_migrate

logger = logging.getLogger(__name__)

def check_configuration(app_configs, **kwargs):
    """Vérifications de configuration différées"""
    errors = []
    if not hasattr(settings, 'CELERY_BROKER_URL'):
        errors.append(Error(
            "CELERY_BROKER_URL non configuré",
            hint="Configurez un broker Redis ou RabbitMQ dans les settings",
            id='location.E001',
        ))
    return errors

class LocationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'location'
    label = 'location'
    verbose_name = "Location de véhicules"

    def ready(self):
        """Initialisation différée après chargement complet"""
        # Enregistrement des checks système
        register(check_configuration, Tags.compatibility)
        
        if self._should_initialize():
            # Double stratégie pour couvrir tous les cas
            autoreload_started.connect(self._delayed_init)
            self._connect_signals()

    def _should_initialize(self):
        """Détermine si on est en mode serveur"""
        import sys
        return 'runserver' in sys.argv or 'gunicorn' in sys.argv or 'celery' in sys.argv

    def _delayed_init(self, sender, **kwargs):
        """Callback après chargement complet de Django"""
        try:
            self._verify_core_models()
            self._load_signals()
            logger.info("Initialisation différée réussie")
        except Exception as e:
            logger.error(f"Erreur d'initialisation différée: {e}", exc_info=True)

    def _connect_signals(self):
        """Connecte les signaux via post_migrate"""
        post_migrate.connect(self._load_signals_on_migrate, sender=self)

    def _load_signals_on_migrate(self, sender, **kwargs):
        """Charge les signaux après migrations"""
        try:
            self._verify_core_models()
            self._load_signals()
        except Exception as e:
            logger.error(f"Erreur post-migrate: {e}", exc_info=True)

    def _verify_core_models(self):
        """Vérifie que les modèles critiques sont chargés"""
        from django.apps import apps
        required_models = [
            'location.Message',
            'location.Conversation',
            settings.AUTH_USER_MODEL
        ]
        
        for model in required_models:
            try:
                apps.get_model(model)
            except LookupError as e:
                logger.error(f"Modèle critique manquant: {model}")
                raise ImportError(f"Modèle {model} non trouvé") from e

    def _load_signals(self):
        """Charge les signaux de manière sécurisée"""
        from django.apps import apps
        
        if not apps.ready:
            logger.warning("Apps pas encore prêtes - report du chargement")
            return

        signals_config = {
            'caution_signals': None,
            'delivery_signals': None,
            'loyalty_signals': None,
            'notification_signals': None,
            'policy_signals': None,
            'portefeuille_signals': None,
            'reservation_signals': None,
            'messaging_signals': {
                'connect_func': 'connect_messaging_signals',
                'verify_model': 'location.Message'
            }
        }

        for sig, config in signals_config.items():
            try:
                module = importlib.import_module(f'location.signals.{sig}')
                
                # Chargement spécial pour messaging_signals
                if config and hasattr(module, config['connect_func']):
                    try:
                        apps.get_model(config['verify_model'])
                        getattr(module, config['connect_func'])()
                        logger.debug(f"Signal {sig} initialisé avec succès")
                    except LookupError as e:
                        logger.error(f"Modèle manquant pour {sig}: {e}")
                        continue
                
                logger.info(f"Signal {sig} chargé")
            except ImportError as e:
                if "No module named" not in str(e):
                    logger.warning(f"Échec partiel du chargement de {sig}: {e}")
            except Exception as e:
                logger.error(f"Erreur dans l'initialisation de {sig}: {e}", exc_info=True)

        # Initialisation spécifique pour la messagerie
        try:
            self._init_messaging_extras()
        except Exception as e:
            logger.error(f"Erreur dans l'init messaging extras: {e}", exc_info=True)

    def _init_messaging_extras(self):
        """Initialisation spécifique pour la messagerie"""
        try:
            from django.db import connection
            Message = self.get_model('Message')
        
            # Vérifie si la table existe dans la base de données
            table_name = Message._meta.db_table
            if table_name in connection.introspection.table_names():
                from .signals.messaging_signals import connect_messaging_signals
                if not connect_messaging_signals():
                    logger.error("Échec connexion signaux messagerie")
                else:
                    logger.info("Extensions messagerie initialisées")
            else:
                logger.warning(f"La table {table_name} n'existe pas encore dans la base de données")
        except Exception as e:
            logger.error(f"Erreur init messaging extras: {e}", exc_info=True)
            raise


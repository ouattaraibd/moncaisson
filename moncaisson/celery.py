from __future__ import absolute_import
import eventlet
eventlet.monkey_patch()  # Doit être la première instruction

import os
import logging
from redis import Redis
from celery import Celery
from celery.signals import worker_shutting_down
from django.conf import settings

# Configuration du logger
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Initialisation Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'moncaisson.settings')
import django
django.setup()

app = Celery('moncaisson')
app.config_from_object('django.conf:settings', namespace='CELERY')

# Configuration optimisée Celery
app.conf.update(
    broker_url='redis://127.0.0.1:6379/0',
    result_backend='redis://127.0.0.1:6379/1',
    worker_pool='eventlet',
    worker_concurrency=4 if settings.DEBUG else 10,
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    broker_connection_retry_on_startup=True,
    broker_pool_limit=10,
    worker_send_task_events=True,
    eventlet_early_patch=True,
    task_soft_time_limit=300,  # 5 minutes
    task_time_limit=600,       # 10 minutes
    worker_max_tasks_per_child=100,
    worker_prefetch_multiplier=1,
)

@worker_shutting_down.connect
def shutdown_handler(sig, how, exitcode, **kwargs):
    """Gestion robuste de l'arrêt du worker"""
    logger.info(f"Arrêt du worker Celery (signal: {sig}, mode: {how}, exitcode: {exitcode})")
    
    try:
        redis_conn = Redis(
            host='127.0.0.1',
            port=6379,
            socket_timeout=5,
            socket_connect_timeout=5
        )
        if redis_conn.ping():
            logger.info("Fermeture propre de la connexion Redis...")
            redis_conn.close()
    except ConnectionError as e:
        logger.error(f"Erreur de connexion Redis: {str(e)}")
    except Exception as e:
        logger.error(f"Erreur inattendue lors de la fermeture Redis: {str(e)}", exc_info=True)
    finally:
        if 'redis_conn' in locals():
            try:
                redis_conn.connection_pool.disconnect()
            except Exception as e:
                logger.warning(f"Échec de déconnexion du pool: {str(e)}")

# Import des tâches après configuration
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

if __name__ == '__main__':
    try:
        logger.info("Démarrage de l'application Celery...")
        app.start()
    except KeyboardInterrupt:
        logger.info("Arrêt demandé par l'utilisateur")
    except Exception as e:
        logger.critical(f"Erreur critique lors du démarrage: {str(e)}", exc_info=True)
        raise


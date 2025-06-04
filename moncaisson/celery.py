import os
from celery import Celery, shared_task
from django.conf import settings
from django.apps import apps

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'moncaisson.settings')

app = Celery('moncaisson')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

@shared_task
def update_all_trust_scores():
    """Tâche périodique pour mettre à jour tous les scores"""
    User = apps.get_model('location', 'User')  # Chargement différé
    from location.services.trust_service import TrustService
    
    for user in User.objects.filter(is_active=True):
        TrustService.update_user_trust_score(user)
        
@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
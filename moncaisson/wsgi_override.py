import os
import sys
from django.core.wsgi import get_wsgi_application

# Chemin absolu vers le répertoire du projet
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'moncaisson.settings')

# Désactive tous les signaux pendant le chargement
os.environ['DJANGO_SKIP_APP_INIT'] = 'true' 

application = get_wsgi_application()

# Réactive les composants après chargement
if 'runserver' in sys.argv:
    from django.apps import apps
    apps.populate(apps.get_app_configs())


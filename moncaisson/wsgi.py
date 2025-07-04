import os
import sys
from pathlib import Path

# Configuration explicite des chemins
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'moncaisson.settings')

# Désactive l'initialisation prématurée
os.environ['DJANGO_SKIP_APP_INIT'] = 'true'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()

print("✓ Application WSGI chargée avec succès")


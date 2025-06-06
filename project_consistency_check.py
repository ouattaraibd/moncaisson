import os
import importlib
from pathlib import Path
import django
import sys

def setup_django():
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'moncaisson.settings')
    django.setup()

def check_imports():
    print("=== Vérification des imports Python ===")
    project_root = Path(__file__).parent
    python_files = list(project_root.glob('**/*.py'))
    
    errors = 0
    
    for py_file in python_files:
        if any(excl in str(py_file) for excl in ['migrations', 'venv', '__pycache__', 'settings.py']):
            continue
            
        rel_path = py_file.relative_to(project_root)
        module_path = str(rel_path).replace('.py', '').replace(os.sep, '.')
        
        try:
            importlib.import_module(module_path)
            print(f"✓ {module_path}")
        except ImportError as e:
            print(f"✗ {module_path}: {str(e)}")
            errors += 1
        except Exception as e:
            print(f"⚠ {module_path}: Erreur inattendue - {str(e)}")
            errors += 1
    
    return errors

def check_templates():
    print("\n=== Vérification des templates ===")
    from django.template.loader import get_template
    from location.models import core_models
    from django.conf import settings
    
    template_dirs = settings.TEMPLATES[0]['DIRS']
    errors = 0
    
    # Vérification des templates de base
    required_templates = [
        'location/base.html',
        'registration/login.html',
        'registration/password_reset_form.html'
    ]
    
    for tpl in required_templates:
        try:
            get_template(tpl)
            print(f"✓ {tpl}")
        except:
            print(f"✗ {tpl} - Template manquant")
            errors += 1
    
    return errors

def check_urls():
    print("\n=== Vérification des URLs ===")
    from django.urls import resolve, reverse, NoReverseMatch
    from moncaisson.urls import urlpatterns as root_urls
    
    errors = 0
    
    # Liste des URLs de base à vérifier
    test_urls = [
        'admin:index',
        'login',
        'logout',
    ]
    
    for url_name in test_urls:
        try:
            reverse(url_name)
            print(f"✓ {url_name}")
        except NoReverseMatch:
            print(f"✗ {url_name} - URL non trouvée")
            errors += 1
    
    return errors

def main():
    setup_django()
    
    total_errors = 0
    total_errors += check_imports()
    total_errors += check_templates()
    total_errors += check_urls()
    
    print("\n=== Résumé ===")
    print(f"Total d'erreurs trouvées: {total_errors}")
    
    if total_errors == 0:
        print("✓ La structure du projet semble cohérente")
    else:
        print("✗ Des problèmes de cohérence ont été détectés")

if __name__ == "__main__":
    main()
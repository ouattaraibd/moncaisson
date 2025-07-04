import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'moncaisson.settings')
import django
django.setup()

from location.models import Voiture
from django.core.files.storage import default_storage

def check_missing_files():
    print("Vérification des fichiers manquants...")
    count = 0
    
    for voiture in Voiture.objects.exclude(photo__exact=''):
        if voiture.photo and not default_storage.exists(voiture.photo.name):
            print(f"Fichier manquant: {voiture.photo.name} (ID Voiture: {voiture.id})")
            voiture.photo = None
            voiture.save()
            count += 1
    
    print(f"{count} fichiers manquants corrigés")

if __name__ == "__main__":
    check_missing_files()


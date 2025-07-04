# location/tests/test_utils.py
import os

def create_test_user(username='testuser', email='test@example.com', password='testpass', user_type='LOUEUR'):
    return User.objects.create_user(
        username=username,
        email=email,
        password=password,
        user_type=user_type
    )

def create_test_voiture(proprietaire, **kwargs):
    defaults = {
        'marque': 'Toyota',
        'modele': 'Corolla',
        'annee': 2020,
        'kilometrage': 10000,
        'nb_places': 5,
        'nb_portes': 5,
        'transmission': 'M',
        'prix_jour': 20000,
        'ville': 'Abidjan'
    }
    defaults.update(kwargs)
    return Voiture.objects.create(proprietaire=proprietaire, **defaults)


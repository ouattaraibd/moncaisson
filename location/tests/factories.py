import factory
from django.contrib.auth import get_user_model
from location.models.core_models import Voiture, User

User = get_user_model()

class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f'user{n}')
    email = factory.Sequence(lambda n: f'user{n}@example.com')
    password = factory.PostGenerationMethodCall('set_password', 'testpass123')
    user_type = 'LOUEUR'

class VoitureFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Voiture

    modele = 'Tesla Model 3'
    marque = 'Tesla'
    annee = 2020
    type_vehicule = 'berline'
    transmission = 'automatique'
    carburant = 'electrique'
    nb_places = 5
    nb_portes = 4
    kilometrage = 0
    disponible = True
    prix_jour = 10000
    climatisation = True
    gps = True
    siege_bebe = False
    bluetooth = True
    avec_chauffeur = False
    caution_required = False
    caution_amount = 0
    ville = 'Paris'
    proprietaire = factory.SubFactory(UserFactory)
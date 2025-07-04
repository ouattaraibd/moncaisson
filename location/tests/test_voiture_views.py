# location/tests/test_voiture_views.py
import os
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from location.models.core_models import User, Voiture, Favoris

User = get_user_model()

class VoitureViewsTest(TestCase):
    def tearDown(self):
        User.objects.all().delete()
        Voiture.objects.all().delete()
        
    def setUp(self):
        self.client = Client()
        
        # Création des utilisateurs
        self.proprietaire = User.objects.create_user(
            username='testuser',
            email='proprio@example.com',
            password=os.getenv('TEST_PWD'),
            user_type='PROPRIETAIRE'
        )
        self.loueur = User.objects.create_user(
            username='testuser',
            email='loueur@example.com',
            password=os.getenv('TEST_PWD'),
            user_type='LOUEUR'
        )
        
        # Création de voitures
        self.voiture1 = Voiture.objects.create(
            proprietaire=self.proprietaire,
            marque='Toyota',
            modele='Corolla',
            annee=2020,
            prix_jour=15000,
            ville='Abidjan'
        )
        self.voiture2 = Voiture.objects.create(
            proprietaire=self.proprietaire,
            marque='Peugeot',
            modele='208',
            annee=2021,
            prix_jour=12000,
            ville='Yamoussoukro',
            disponible=False
        )
        
    def test_liste_voitures(self):
        url = reverse('voiture_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['voitures']), 1)  # Seule la voiture disponible
        self.assertContains(response, 'Toyota Corolla')
        self.assertNotContains(response, 'Peugeot 208')  # Non disponible
        
    def test_voiture_detail(self):
        url = reverse('voiture_detail', args=[self.voiture1.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['voiture'], self.voiture1)
        self.assertContains(response, 'Toyota Corolla')
        
    def test_ajouter_favoris(self):
        self.client.login(email='loueur@example.com', password=os.getenv('TEST_PWD'))
        
        url = reverse('ajouter_favoris', args=[self.voiture1.id])
        response = self.client.get(url)
        
        # Vérification de la création du favori
        favori = Favoris.objects.filter(
            utilisateur=self.loueur,
            voiture=self.voiture1
        ).exists()
        self.assertTrue(favori)
        
        # Vérification du message
        messages = list(response.wsgi_request._messages)
        self.assertEqual(len(messages), 1)
        self.assertIn("ajouté aux favoris", str(messages[0]))
        
    def test_ajouter_voiture_proprietaire(self):
        self.client.login(email='proprio@example.com', password=os.getenv('TEST_PWD'))
        
        url = reverse('ajouter_voiture')
        
        # Test GET
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # Test POST
        form_data = {
            'marque': 'Renault',
            'modele': 'Clio',
            'annee': 2019,
            'prix_jour': 10000,
            'ville': 'Abidjan',
            'type_vehicule': 'citadine',
            'transmission': 'M',
            'nb_places': 5,
            'description': 'Voiture en excellent état'
        }
        response = self.client.post(url, form_data)
        self.assertEqual(response.status_code, 302)  # Redirection
        
        # Vérification de la création de la voiture
        voiture = Voiture.objects.filter(marque='Renault').first()
        self.assertIsNotNone(voiture)
        self.assertEqual(voiture.proprietaire, self.proprietaire)


# location/tests/test_reservation_views.py
import os
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from location.models.core_models import User, Voiture, Reservation

User = get_user_model()

class ReservationViewsTest(TestCase):
    def tearDown(self):
        User.objects.all().delete()
        Voiture.objects.all().delete()
        Reservation.objects.all().delete()
        
    def setUp(self):
        self.client = Client()
        self.today = timezone.now().date()
        
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
        
        # Création d'une voiture
        self.voiture = Voiture.objects.create(
            proprietaire=self.proprietaire,
            marque='Toyota',
            modele='Corolla',
            annee=2020,
            prix_jour=15000,
            ville='Abidjan'
        )
        
        # Connexion du loueur
        self.client.login(email='loueur@example.com', password=os.getenv('TEST_PWD'))
        
    def test_reserver_voiture(self):
        url = reverse('reserver_voiture', args=[self.voiture.id])
        
        # Test GET
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # Test POST avec dates valides
        form_data = {
            'date_debut': (self.today + timezone.timedelta(days=1)).strftime('%Y-%m-%d'),
            'date_fin': (self.today + timezone.timedelta(days=3)).strftime('%Y-%m-%d'),
            'avec_chauffeur': False
        }
        response = self.client.post(url, form_data)
        self.assertEqual(response.status_code, 302)  # Redirection vers paiement
        
        # Vérification de la création de la réservation
        reservation = Reservation.objects.filter(voiture=self.voiture).first()
        self.assertIsNotNone(reservation)
        self.assertEqual(reservation.client, self.loueur)
        self.assertEqual(reservation.duree, 2)  # 2 jours
        
    def test_reservation_dates_invalides(self):
        url = reverse('reserver_voiture', args=[self.voiture.id])
        
        # Date de fin avant date de début
        form_data = {
            'date_debut': (self.today + timezone.timedelta(days=3)).strftime('%Y-%m-%d'),
            'date_fin': (self.today + timezone.timedelta(days=1)).strftime('%Y-%m-%d'),
            'avec_chauffeur': False
        }
        response = self.client.post(url, form_data)
        self.assertEqual(response.status_code, 200)  # Reste sur la page
        self.assertContains(response, "Date fin invalide")
        
    def test_mes_reservations(self):
        # Création d'une réservation
        Reservation.objects.create(
            voiture=self.voiture,
            client=self.loueur,
            date_debut=self.today + timezone.timedelta(days=1),
            date_fin=self.today + timezone.timedelta(days=3),
            montant_paye=30000,
            statut='confirme'
        )
        
        url = reverse('mes_reservations')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['reservations']), 1)
        self.assertContains(response, 'Toyota Corolla')


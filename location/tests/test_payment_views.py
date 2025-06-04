# location/tests/test_payment_views.py
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from location.models.core_models import (
    User, Voiture, Reservation, Paiement, Portefeuille
)
from decimal import Decimal

User = get_user_model()

class PaymentViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        
        # Création des utilisateurs
        self.proprietaire = User.objects.create_user(
            username='testuser',
            email='proprio@example.com',
            password='testpass123',
            user_type='PROPRIETAIRE'
        )
        self.loueur = User.objects.create_user(
            username='testuser',
            email='loueur@example.com',
            password='testpass123',
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
        
        # Création d'une réservation
        self.reservation = Reservation.objects.create(
            voiture=self.voiture,
            client=self.loueur,
            date_debut='2023-01-01',
            date_fin='2023-01-03',
            montant_paye=30000,
            statut='attente_paiement'
        )
        
        # Connexion du loueur
        self.client.login(email='loueur@example.com', password='testpass123')
        
    def test_choisir_methode_paiement(self):
        url = reverse('choisir_methode_paiement', args=[self.reservation.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choisissez votre méthode de paiement")
        
    def test_process_paiement_portefeuille(self):
        # Création d'un portefeuille avec solde suffisant
        Portefeuille.objects.create(proprietaire=self.loueur, solde=50000)
        
        url = reverse('process_paiement', args=[self.reservation.id])
        response = self.client.post(url, {'methode': 'PORTEFEUILLE'})
        
        # Vérification de la redirection
        self.assertEqual(response.status_code, 302)
        
        # Vérification de la mise à jour de la réservation
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.statut, 'payee')
        
        # Vérification du paiement créé
        paiement = Paiement.objects.filter(reservation=self.reservation).first()
        self.assertIsNotNone(paiement)
        self.assertEqual(paiement.statut, 'reussi')
        
        # Vérification des soldes
        portefeuille_loueur = Portefeuille.objects.get(proprietaire=self.loueur)
        self.assertLess(portefeuille_loueur.solde, 50000)  # Doit avoir été débité
        
        portefeuille_proprio = Portefeuille.objects.get(proprietaire=self.proprietaire)
        self.assertGreater(portefeuille_proprio.solde, 0)  # Doit avoir été crédité

    def test_process_paiement_solde_insuffisant(self):
        # Création d'un portefeuille avec solde insuffisant
        Portefeuille.objects.create(proprietaire=self.loueur, solde=1000)
        
        url = reverse('process_paiement', args=[self.reservation.id])
        response = self.client.post(url, {'methode': 'PORTEFEUILLE'})
        
        # Vérification du message d'erreur
        messages = list(response.context['messages'])
        self.assertEqual(len(messages), 1)
        self.assertIn("Solde insuffisant", str(messages[0]))
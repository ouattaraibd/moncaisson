# tests/test_integration.py
import os
from django.test import TestCase
from django.urls import reverse
from location.models.core_models import User, Voiture, Reservation

class FullWorkflowTest(TestCase):
    def test_full_reservation_flow(self):
        # 1. Création utilisateur
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        
        # 2. Création voiture
        voiture = Voiture.objects.create(
            proprietaire=user,
            marque='Renault',
            modele='Clio',
            annee=2022,
            kilometrage=5000,
            nb_places=5,
            prix_jour=18000
        )
        
        # 3. Création réservation
        reservation = Reservation.objects.create(
            voiture=voiture,
            client=user,
            date_debut='2023-02-01',
            date_fin='2023-02-05',
            montant_total=72000
        )
        
        # 4. Simulation paiement
        self.client.login(username='testuser', password=os.getenv('TEST_PWD'))
        response = self.client.post(
            reverse('choisir_methode_paiement', args=[reservation.id]),
            {'methode': 'PORTEFEUILLE'},
            follow=True
        )
        
        # Vérifications finales
        self.assertEqual(response.status_code, 200)
        reservation.refresh_from_db()
        self.assertEqual(reservation.statut, 'confirme')


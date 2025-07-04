# tests/test_payment_views.py
import os
from django.test import TestCase, Client
from django.urls import reverse
from location.models.core_models import User, Reservation, Voiture

class PaymentViewsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.client = Client()
        cls.user = User.objects.create_user(
            username='testuser',
            email='user@example.com',
            password=os.getenv('TEST_PWD')
        )
        cls.voiture = Voiture.objects.create(
            proprietaire=cls.user,
            marque='Peugeot',
            modele='208',
            annee=2021,
            kilometrage=10000,
            nb_places=5,
            prix_jour=20000
        )
        cls.reservation = Reservation.objects.create(
            voiture=cls.voiture,
            client=cls.user,
            date_debut='2023-01-01',
            date_fin='2023-01-03',
            montant_total=60000
        )

    def test_choisir_methode_paiement_view(self):
        self.client.login(username='testuser', password=os.getenv('TEST_PWD'))
        response = self.client.get(
            reverse('choisir_methode_paiement', args=[self.reservation.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choisissez votre méthode de paiement")

    def test_payment_redirects(self):
        self.client.login(username='testuser', password=os.getenv('TEST_PWD'))
        response = self.client.post(
            reverse('choisir_methode_paiement', args=[self.reservation.id]),
            {'methode': 'PORTEFEUILLE'},
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.redirect_chain[0][1], 301)  # Vérifie que ce n'est pas une 301


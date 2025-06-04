from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from location.models.core_models import Reservation, Voiture
from unittest.mock import patch
import datetime

User = get_user_model()

class PaymentWorkflowTest(TestCase):
    def setUp(self):
        self.client = Client()
        
        # Création utilisateur
        self.user = User.objects.create_user(
            username='testuser',
            email='test@user.com',
            password='testpass123',
            user_type='LOUEUR'
        )
        
        # Création voiture avec TOUS les champs obligatoires
        self.voiture = Voiture.objects.create(
            modele='Tesla Model 3',
            marque='Tesla',
            annee=2020,
            type_vehicule='berline',
            transmission='automatique',
            carburant='electrique',
            nb_places=5,
            nb_portes=4,
            kilometrage=0,
            disponible=True,
            prix_jour=10000,
            proprietaire=self.user,
            # Champs optionnels avec valeurs par défaut
            climatisation=True,
            gps=True,
            siege_bebe=False,
            bluetooth=True,
            avec_chauffeur=False,
            caution_required=False,
            caution_amount=0,
            ville='Paris'
        )
        
        # Création réservation
        self.reservation = Reservation.objects.create(
            client=self.user,
            voiture=self.voiture,
            montant_total=50000,
            date_debut=datetime.date.today(),
            date_fin=datetime.date.today() + datetime.timedelta(days=7),
            statut='attente_paiement'
        )

    @patch('stripe.PaymentIntent.create')
    def test_stripe_payment_flow(self, mock_stripe):
        mock_stripe.return_value = {
            'id': 'pi_test123',
            'status': 'succeeded',
            'client_secret': 'test_secret'
        }

        self.client.force_login(self.user)
        response = self.client.post(
            reverse('choisir_methode_paiement', args=[self.reservation.id]),
            {'methode': 'CARTE'},
            follow=True
        )
        self.assertEqual(response.status_code, 200)

    @patch('requests.post')
    def test_orange_money_flow(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            'payment_url': 'https://orange-money.test/checkout'
        }

        self.client.force_login(self.user)
        response = self.client.post(
            reverse('choisir_methode_paiement', args=[self.reservation.id]),
            {'methode': 'ORANGE'},
            follow=True
        )
        self.assertEqual(response.status_code, 200)
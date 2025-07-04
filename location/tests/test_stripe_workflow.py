import os
import json
from unittest.mock import patch
from django.test import TestCase
from django.urls import reverse
from location.views.payment_views import initier_paiement 
from location.models.core_models import Reservation, User, Voiture

class StripePaymentTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@user.com',
            username='testuser',
            password=os.getenv('TEST_PWD'),
            user_type='LOUEUR'
        )
        self.voiture = Voiture.objects.create(
            modele='Tesla Model 3',
            prix_jour=10000  # 10,000 XOF
        )
        self.reservation = Reservation.objects.create(
            client=self.user,
            voiture=self.voiture,
            montant_total=50000  # 50,000 XOF
        )

    @patch('stripe.PaymentIntent.create')
    def test_complete_stripe_flow(self, mock_stripe):
        # 1. Mock Stripe
        mock_stripe.return_value = {
            'id': 'pi_test123',
            'status': 'requires_confirmation'
        }

        # 2. Initier paiement
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('initier_paiement', args=[self.reservation.id]),
            {'payment_method': 'carte'}
        )
        self.assertEqual(response.status_code, 302)  # Redirection attendue

        # 3. Simuler webhook Stripe
        webhook_url = reverse('stripe_webhook')
        webhook_data = {
            "id": "evt_test",
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_test123",
                    "status": "succeeded"
                }
            }
        }
        response = self.client.post(
            webhook_url,
            data=json.dumps(webhook_data),
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='fake_sig'
        )
        self.assertEqual(response.status_code, 200)

        # 4. Vérifier la réservation
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.statut, 'confirme')


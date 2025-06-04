# location/tests/integration_tests.py
from django.test import TestCase
from django.urls import reverse
from location.models import User, Voiture, Reservation

class ReservationFlowTest(TestCase):
    def test_complete_reservation_flow(self):
        # 1. Création utilisateur et voiture
        user = User.objects.create_user(
            username='loueur',
            password='testpass',
            user_type='LOUEUR',
            phone='+2250102030405'
        )
        proprio = User.objects.create_user(
            username='proprio',
            password='testpass',
            user_type='PROPRIETAIRE'
        )
        voiture = Voiture.objects.create(
            proprietaire=proprio,
            marque='Toyota',
            modele='Corolla',
            annee=2020,
            prix_jour=30000,
            ville='Abidjan'
        )
        
        # 2. Connexion
        self.client.login(username='loueur', password='testpass')
        
        # 3. Réservation
        response = self.client.post(reverse('reserver_voiture', args=[voiture.id]), {
            'date_debut': '2023-12-01',
            'date_fin': '2023-12-03'
        })
        self.assertEqual(response.status_code, 302)
        
        # 4. Vérification création réservation
        reservation = Reservation.objects.first()
        self.assertEqual(reservation.voiture, voiture)
        self.assertEqual(reservation.client, user)
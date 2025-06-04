# location/tests/test_integration.py
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from location.models.core_models import (
    User, Voiture, Reservation, Paiement, Portefeuille
)

User = get_user_model()

class CompleteFlowTest(TestCase):
    """Test du flux complet: Inscription -> Ajout voiture -> Réservation -> Paiement"""
    
    def setUp(self):
        self.client = Client()
        self.today = timezone.now().date()
        
    def test_complete_flow(self):
        # 1. Inscription propriétaire
        register_url = reverse('register_proprietaire')
        form_data = {
            'username': 'testuser',
            'email': 'proprio@example.com',
            'first_name': 'Jean',
            'last_name': 'Dupont',
            'phone': '+2250707070707',
            'password1': 'Complexe123!',
            'password2': 'Complexe123!',
            'user_type': 'PROPRIETAIRE',
            'cin': '99X99999',
            'address': '123 Rue Test'
        }
        response = self.client.post(register_url, form_data)
        self.assertEqual(response.status_code, 302)  # Redirection
        
        # 2. Connexion
        self.client.login(email='proprio@example.com', password='Complexe123!')
        
        # 3. Ajout d'une voiture
        add_car_url = reverse('ajouter_voiture')
        car_data = {
            'marque': 'Toyota',
            'modele': 'Corolla',
            'annee': 2020,
            'prix_jour': 15000,
            'ville': 'Abidjan',
            'type_vehicule': 'berline',
            'transmission': 'A',
            'nb_places': 5
        }
        response = self.client.post(add_car_url, car_data)
        self.assertEqual(response.status_code, 302)
        
        voiture = Voiture.objects.first()
        self.assertEqual(voiture.marque, 'Toyota')
        
        # 4. Déconnexion propriétaire
        self.client.logout()
        
        # 5. Inscription loueur
        form_data = {
            'email': 'loueur@example.com',
            'first_name': 'Marie',
            'last_name': 'Martin',
            'phone': '+22501020304',
            'password1': 'Loueur123!',
            'password2': 'Loueur123!',
            'user_type': 'LOUEUR'
        }
        response = self.client.post(reverse('register_loueur'), form_data)
        self.assertEqual(response.status_code, 302)
        
        # 6. Connexion loueur
        self.client.login(email='loueur@example.com', password='Loueur123!')
        
        # 7. Réservation
        reserve_url = reverse('reserver_voiture', args=[voiture.id])
        reserve_data = {
            'date_debut': (self.today + timezone.timedelta(days=1)).strftime('%Y-%m-%d'),
            'date_fin': (self.today + timezone.timedelta(days=3)).strftime('%Y-%m-%d'),
            'avec_chauffeur': False
        }
        response = self.client.post(reserve_url, reserve_data)
        self.assertEqual(response.status_code, 302)
        
        reservation = Reservation.objects.first()
        self.assertEqual(reservation.montant_paye, 30000)  # 2 jours * 15000
        
        # 8. Création portefeuille avec solde
        Portefeuille.objects.create(proprietaire=User.objects.get(email='loueur@example.com'), solde=50000)
        
        # 9. Paiement
        payment_url = reverse('process_paiement', args=[reservation.id])
        response = self.client.post(payment_url, {'methode': 'PORTEFEUILLE'})
        self.assertEqual(response.status_code, 302)
        
        # Vérifications finales
        reservation.refresh_from_db()
        self.assertEqual(reservation.statut, 'payee')
        
        paiement = Paiement.objects.first()
        self.assertEqual(paiement.methode, 'PORTEFEUILLE')
        
        portefeuille_loueur = Portefeuille.objects.get(proprietaire__email='loueur@example.com')
        self.assertLess(portefeuille_loueur.solde, 50000)  # Doit avoir été débité
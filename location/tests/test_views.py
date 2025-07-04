import os
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import date, timedelta
from location.models import (
    User,
    Voiture, 
    Reservation, 
    DeliveryOption,
    Paiement
)

class AuthViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user_data = {
            'username': 'testuser',
            'password': 'testpass123',
            'user_type': 'LOUEUR',
            'phone': '+2250700000000',
            'city': 'Abidjan'
        }
        self.user = get_user_model().objects.create_user(**self.user_data)

    def test_connexion_view_success(self):
        """Teste la vue de connexion avec des identifiants valides"""
        response = self.client.post(reverse('connexion'), {
            'username': 'testuser',
            'password': 'testpass123'
        }, follow=True)
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['user'].is_authenticated)

    def test_connexion_view_failure(self):
        """Teste la vue de connexion avec des identifiants invalides"""
        response = self.client.post(reverse('connexion'), {
            'username': 'testuser',
            'password': 'wrongpassword'
        }, follow=True)
        
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['user'].is_authenticated)
        self.assertContains(response, "Identifiants incorrects")

    def test_register_loueur_view_success(self):
        """Teste l'inscription réussie d'un loueur"""
        response = self.client.post(reverse('register_loueur'), {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password1': 'Complexpass123!',
            'password2': 'Complexpass123!',
            'phone': '+2250102030405',
            'city': 'Abidjan',
            'user_type': 'LOUEUR',
            'terms_accepted': 'on'
        }, follow=True)
    
        self.assertEqual(response.status_code, 200)
        self.assertTrue(get_user_model().objects.filter(username='newuser').exists())
    
        # Vérification de la création du profil de fidélité
        user = get_user_model().objects.get(username='newuser')
        self.assertTrue(hasattr(user, 'loyalty_profile'))
        self.assertContains(response, "Votre compte a été créé avec succès")

    def test_register_loueur_view_failure(self):
        """Teste l'échec d'inscription avec des données invalides"""
        response = self.client.post(reverse('register_loueur'), {
            'username': 'newuser',
            'password1': 'simple',
            'password2': 'simple',
            'phone': 'invalid',
            'user_type': 'LOUEUR'
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertFalse(get_user_model().objects.filter(username='newuser').exists())
        self.assertContains(response, "Ce formulaire contient des erreurs")


class ReservationViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        
        # Création des utilisateurs
        self.proprietaire = get_user_model().objects.create_user(
            username='proprio',
            email='test@example.com',
            password='testpass',
            user_type='PROPRIETAIRE',
            phone='+2250100000000',
            city='Abidjan'
        )
        
        self.loueur = get_user_model().objects.create_user(
            username='loueur',
            email='test@example.com',
            password='testpass',
            user_type='LOUEUR',
            phone='+2250700000000',
            city='Abidjan'
        )
        
        # Création d'une voiture avec tous les champs requis
        self.voiture = Voiture.objects.create(
            proprietaire=self.proprietaire,
            marque='Toyota',
            modele='Corolla',
            annee=2020,
            prix_jour=25000,
            ville='Abidjan',
            kilometrage=10000,
            nb_places=5,
            nb_portes=4,
            carburant='essence',
            transmission='A',
            type_vehicule='berline'
        )
        
        # Connexion du loueur
        self.client.force_login(self.loueur)

    def test_reserver_voiture_view_get(self):
        """Teste l'accès à la page de réservation"""
        url = reverse('reserver_voiture', args=[self.voiture.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'reservation/reservation.html')
        self.assertEqual(response.context['voiture'], self.voiture)

    def test_reservation_creation_success(self):
        """Teste la création réussie d'une réservation"""
        url = reverse('reserver_voiture', args=[self.voiture.id])
        tomorrow = date.today() + timedelta(days=1)
        end_date = tomorrow + timedelta(days=3)
    
        response = self.client.post(url, {
            'date_debut': tomorrow.strftime('%Y-%m-%d'),
            'date_fin': end_date.strftime('%Y-%m-%d'),
            'avec_livraison': False
        }, follow=True)
    
        self.assertEqual(response.status_code, 200)
        reservation = Reservation.objects.filter(voiture=self.voiture, client=self.loueur).first()
        self.assertIsNotNone(reservation)
        self.assertEqual(reservation.statut, 'attente_paiement')
        self.assertTrue(reservation.est_payable)
        self.assertContains(response, "Réservation créée avec succès")

    def test_reservation_creation_failure(self):
        """Teste l'échec de création de réservation avec dates invalides"""
        url = reverse('reserver_voiture', args=[self.voiture.id])
        
        # Date de fin avant date de début
        response = self.client.post(url, {
            'date_debut': '2023-12-10',
            'date_fin': '2023-12-01'
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Reservation.objects.filter(voiture=self.voiture).exists())
        self.assertContains(response, "La date de fin doit être postérieure")

    def test_reservation_unauthenticated(self):
        """Teste l'accès à la vue de réservation sans être connecté"""
        self.client.logout()
        url = reverse('reserver_voiture', args=[self.voiture.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, f'/connexion/?next={url}')


class PaymentViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        
        # Création des utilisateurs
        self.proprietaire = get_user_model().objects.create_user(
            username='proprio',
            email='test@example.com',
            password='testpass',
            user_type='PROPRIETAIRE',
            phone='+2250100000000',
            city='Abidjan'
        )
        
        self.loueur = get_user_model().objects.create_user(
            username='loueur',
            email='test@example.com',
            password='testpass',
            user_type='LOUEUR',
            phone='+2250700000000',
            city='Abidjan'
        )
        
        # Création d'une voiture avec tous les champs requis
        self.voiture = Voiture.objects.create(
            proprietaire=self.proprietaire,
            marque='Toyota',
            modele='Corolla',
            annee=2020,
            prix_jour=25000,
            ville='Abidjan',
            kilometrage=10000,
            nb_places=5,
            nb_portes=4,
            carburant='essence',
            transmission='A',
            type_vehicule='berline'
        )
        
        # Création d'une réservation
        self.reservation = Reservation.objects.create(
            voiture=self.voiture,
            client=self.loueur,
            date_debut=date.today() + timedelta(days=1),
            date_fin=date.today() + timedelta(days=3),
            montant_paye=75000,
            statut='attente_paiement'
        )
        
        # Connexion du loueur
        self.client.force_login(self.loueur)

    def test_initier_paiement_view_get(self):
        """Teste l'accès à la page de paiement"""
        url = reverse('initier_paiement', args=[self.reservation.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'paiement/recapitulatif.html')
        self.assertEqual(response.context['reservation'], self.reservation)

    def test_initier_paiement_view_post(self):
        """Teste la soumission du formulaire de paiement"""
        url = reverse('initier_paiement', args=[self.reservation.id])
        response = self.client.post(url, {
            'methode_paiement': 'ORANGE',
            'terms_accepted': 'on'
        }, follow=True)
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Paiement.objects.filter(reservation=self.reservation).exists())
        self.assertContains(response, "Paiement initié avec succès")

    def test_initier_paiement_wrong_user(self):
        """Teste l'accès à la vue de paiement par un utilisateur non autorisé"""
        other_user = get_user_model().objects.create_user(
            username='otheruser',
            email='test@example.com',
            password='testpass',
            user_type='LOUEUR',
            phone='+2250500000000',
            city='Abidjan'
        )
        self.client.force_login(other_user)
        
        url = reverse('initier_paiement', args=[self.reservation.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 403)  # Forbidden

    def test_paiement_confirmation_view(self):
        """Teste la vue de confirmation de paiement"""
        paiement = Paiement.objects.create(
            reservation=self.reservation,
            methode='ORANGE',
            montant=75000,
            devise_origine='XOF',
            statut='REUSSI'
        )
        
        url = reverse('confirmation_paiement', args=[paiement.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'paiement/confirmation_paiement.html')
        self.assertEqual(response.context['paiement'], paiement)
        



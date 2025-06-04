from rest_framework.test import APITestCase,  APIClient
from rest_framework import status
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from location.models import (
    DeliveryOption, 
    DeliveryRequest, 
    User, 
    Voiture, 
    Reservation
)

class DeliveryAPITest(APITestCase):
    def setUp(self):
        # Création des options de livraison
        self.standard_option = DeliveryOption.objects.create(
            name='Standard Delivery',
            delivery_type='STANDARD',
            price=5000,
            description='Livraison en 24h',
            is_active=True
        )
        
        self.express_option = DeliveryOption.objects.create(
            name='Express Delivery',
            delivery_type='EXPRESS',
            price=10000,
            description='Livraison en 2h',
            is_active=True
        )
        
        # Création des utilisateurs
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            user_type='LOUEUR',
            phone='+2250700000000',
            city='Abidjan'
        )
        
        self.proprietaire = User.objects.create_user(
            username='proprio',
            password='testpass',
            user_type='PROPRIETAIRE',
            phone='+2250100000000',
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
            client=self.user,
            date_debut=timezone.now().date() + timedelta(days=1),
            date_fin=timezone.now().date() + timedelta(days=3),
            montant_paye=75000,
            statut='confirme'
        )
        
        # Authentification
        self.client.force_authenticate(user=self.user)

    def test_list_delivery_options(self):
        """Teste la liste des options de livraison disponibles"""
        url = reverse('delivery-options-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        
        # Vérification des données retournées
        option_data = response.data[0]
        self.assertIn('id', option_data)
        self.assertIn('name', option_data)
        self.assertIn('delivery_type', option_data)
        self.assertIn('price', option_data)
        self.assertIn('description', option_data)

    def test_create_delivery_request(self):
        """Teste la création d'une demande de livraison"""
        url = reverse('delivery-requests-list')
        data = {
            'reservation': self.reservation.id,
            'delivery_option': self.standard_option.id,
            'delivery_address': 'Cocody, Rue des Jardins, Abidjan',
            'requested_date': (timezone.now() + timedelta(days=1)).isoformat(),
            'special_instructions': 'Sonner à l\'arrivée'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(DeliveryRequest.objects.count(), 1)
        
        # Vérification des données enregistrées
        delivery = DeliveryRequest.objects.first()
        self.assertEqual(delivery.user, self.user)
        self.assertEqual(delivery.status, 'PENDING')
        self.assertEqual(delivery.delivery_address, data['delivery_address'])

    def test_create_delivery_request_invalid_dates(self):
        """Teste la création avec des dates invalides"""
        url = reverse('delivery-requests-list')
        
        # Date antérieure à aujourd'hui
        data = {
            'reservation': self.reservation.id,
            'delivery_option': self.standard_option.id,
            'delivery_address': 'Cocody, Abidjan',
            'requested_date': (timezone.now() - timedelta(days=1)).isoformat()
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('requested_date', response.data)

    def test_delivery_request_status_update_by_owner(self):
        """Teste la mise à jour du statut par le propriétaire"""
        delivery = DeliveryRequest.objects.create(
            reservation=self.reservation,
            user=self.user,
            voiture=self.voiture,
            delivery_option=self.standard_option,
            delivery_address='Cocody, Abidjan',
            status='PENDING'
        )
        
        # Authentification en tant que propriétaire
        self.client.force_authenticate(user=self.proprietaire)
        
        url = reverse('delivery-requests-detail', args=[delivery.id])
        data = {'status': 'ACCEPTED'}
        
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, 'ACCEPTED')
        self.assertEqual(delivery.handled_by, self.proprietaire)

    def test_delivery_request_status_update_unauthorized(self):
        """Teste la mise à jour par un utilisateur non autorisé"""
        delivery = DeliveryRequest.objects.create(
            reservation=self.reservation,
            user=self.user,
            voiture=self.voiture,
            delivery_option=self.standard_option,
            delivery_address='Cocody, Abidjan',
            status='PENDING'
        )
        
        # Création d'un autre utilisateur
        other_user = User.objects.create_user(
            username='otheruser',
            password='testpass',
            user_type='LOUEUR',
            phone='+2250500000000',
            city='Abidjan'
        )
        
        self.client.force_authenticate(user=other_user)
        
        url = reverse('delivery-requests-detail', args=[delivery.id])
        data = {'status': 'ACCEPTED'}
        
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_delivery_request_detail(self):
        """Teste la récupération des détails d'une demande"""
        delivery = DeliveryRequest.objects.create(
            reservation=self.reservation,
            user=self.user,
            voiture=self.voiture,
            delivery_option=self.standard_option,
            delivery_address='Cocody, Abidjan',
            status='PENDING'
        )
        
        url = reverse('delivery-requests-detail', args=[delivery.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], delivery.id)
        self.assertEqual(response.data['status'], 'PENDING')

    def test_list_user_delivery_requests(self):
        """Teste la liste des demandes de l'utilisateur"""
        # Création de plusieurs demandes
        DeliveryRequest.objects.create(
            reservation=self.reservation,
            user=self.user,
            voiture=self.voiture,
            delivery_option=self.standard_option,
            delivery_address='Cocody, Abidjan',
            status='PENDING'
        )
        
        DeliveryRequest.objects.create(
            reservation=self.reservation,
            user=self.user,
            voiture=self.voiture,
            delivery_option=self.express_option,
            delivery_address='Plateau, Abidjan',
            status='COMPLETED'
        )
        
        url = reverse('delivery-requests-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_delivery_request_deletion(self):
        """Teste la suppression d'une demande"""
        delivery = DeliveryRequest.objects.create(
            reservation=self.reservation,
            user=self.user,
            voiture=self.voiture,
            delivery_option=self.standard_option,
            delivery_address='Cocody, Abidjan',
            status='PENDING'
        )
        
        url = reverse('delivery-requests-detail', args=[delivery.id])
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(DeliveryRequest.objects.count(), 0)
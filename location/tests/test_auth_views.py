# location/tests/test_auth_views.py
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from location.models.core_models import User, ProprietaireProfile

User = get_user_model()

class AuthViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'testpass123',
            'first_name': 'John',
            'last_name': 'Doe',
            'phone': '+2250707070707'
        }
        
    def test_register_proprietaire(self):
        url = reverse('register_proprietaire')
        
        # Test GET
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "S'inscrire comme propriétaire")
        
        # Test POST avec données valides
        form_data = {
            **self.user_data,
            'password2': 'testpass123',
            'user_type': 'PROPRIETAIRE',
            'cin': '99X99999',
            'address': '123 Rue Test'
        }
        response = self.client.post(url, form_data)
        self.assertEqual(response.status_code, 302)  # Redirection
        
        # Vérification de la création de l'utilisateur
        user = User.objects.get(email='test@example.com')
        self.assertEqual(user.user_type, 'PROPRIETAIRE')
        self.assertTrue(hasattr(user, 'proprietaire_profile'))
        
    def test_login_view(self):
        # Création d'un utilisateur de test
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        url = reverse('connexion')
        
        # Test GET
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # Test POST avec identifiants valides
        response = self.client.post(url, {
            'username': 'test@example.com',
            'password': 'testpass123'
        })
        self.assertEqual(response.status_code, 302)  # Redirection après connexion
        
        # Test POST avec identifiants invalides
        response = self.client.post(url, {
            'username': 'test@example.com',
            'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, 200)  # Reste sur la page
        self.assertContains(response, "Identifiants incorrects")

class ProprietaireViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='proprio@example.com',
            password='testpass123',
            user_type='PROPRIETAIRE'
        )
        self.client.login(email='proprio@example.com', password='testpass123')
        
    def test_upload_documents_view(self):
        url = reverse('upload_documents')
        
        # Test GET
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # Test POST avec fichier (simulé)
        with tempfile.NamedTemporaryFile(suffix='.pdf') as tmp:
            response = self.client.post(url, {
                'assurance_document': tmp,
                'carte_grise_document': tmp
            })
            self.assertEqual(response.status_code, 302)  # Redirection
            
            # Vérification de la mise à jour du profil
            profile = ProprietaireProfile.objects.get(user=self.user)
            self.assertTrue(profile.assurance_document)
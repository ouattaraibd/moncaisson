import os
from django.test import TestCase
from django.contrib.auth import get_user_model
from location.services.trust_service import TrustService
from location.models import Voiture, Reservation

User = get_user_model()

class TrustServiceTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass',
            user_type='LOUEUR'
        )
        
    def test_calculate_new_user_score(self):
        """Teste le score d'un nouvel utilisateur"""
        score = TrustService.calculate_trust_score(self.user)
        self.assertEqual(score, 50)  # Score initial
        
    def test_score_after_verification(self):
        """Teste l'impact de la vérification sur le score"""
        self.user.is_verified = True
        self.user.save()
        
        score = TrustService.calculate_trust_score(self.user)
        self.assertGreater(score, 50)  # Doit être > score initial
        
    def test_update_method(self):
        """Teste la méthode de mise à jour"""
        initial_score = self.user.trust_score
        new_score = TrustService.update_user_trust_score(self.user)
        
        self.assertNotEqual(initial_score, new_score)
        self.assertEqual(self.user.trust_score, new_score)
        
    def test_trust_categories(self):
        """Teste les catégories de confiance"""
        self.assertEqual(TrustService.get_trust_category(score=85), 'excellent')
        self.assertEqual(TrustService.get_trust_category(score=65), 'bon')
        self.assertEqual(TrustService.get_trust_category(score=45), 'moyen')
        self.assertEqual(TrustService.get_trust_category(score=30), 'a_ameliorer')


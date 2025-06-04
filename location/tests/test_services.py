# location/tests/test_services.py
from django.test import TestCase
from location.models.core_models import User
from location.services.trust_service import TrustService

class TrustServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            user_type='LOUEUR'
        )
        
    def test_calculate_trust_score(self):
        # Cas de base - utilisateur nouveau
        score = TrustService.calculate_trust_score(self.user)
        self.assertEqual(score, 50)  # Score initial
        
        # Ajout de métriques positives
        self.user.trust_metrics = {
            'completed_reservations': 5,
            'positive_reviews': 3,
            'account_age_days': 30
        }
        score = TrustService.calculate_trust_score(self.user)
        self.assertGreater(score, 50)
        
        # Ajout de métriques négatives
        self.user.trust_metrics['cancellations'] = 2
        score = TrustService.calculate_trust_score(self.user)
        self.assertLess(score, 70)
        
    def test_update_trust_score(self):
        initial_score = self.user.trust_score
        TrustService.update_trust_score(self.user)
        self.assertNotEqual(self.user.trust_score, initial_score)
        self.assertTrue(50 <= self.user.trust_score <= 100)
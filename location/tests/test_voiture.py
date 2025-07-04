# tests/test_voiture.py
import os
from django.test import TestCase
from location.models.core_models import User, Voiture

class VoitureModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='proprio',
            email='proprio@example.com',
            password=os.getenv('TEST_PWD'),
            user_type='PROPRIETAIRE'
        )

    def test_voiture_creation(self):
        voiture = Voiture.objects.create(
            proprietaire=self.user,
            marque='Toyota',
            modele='Corolla',
            annee=2020,
            kilometrage=15000,  # Test du champ corrigé
            nb_places=5,
            prix_jour=25000
        )
        self.assertEqual(voiture.kilometrage, 15000)
        self.assertTrue(voiture.disponible)


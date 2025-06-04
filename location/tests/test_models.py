# location/tests/test_models.py
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from location.models.core_models import (
    User, ProprietaireProfile, Voiture, Reservation, 
    Paiement, Portefeuille, Transaction
)
import tempfile
from django.core.files.uploadedfile import SimpleUploadedFile

class UserModelTest(TestCase):
    def test_create_user(self):
        user = User.objects.create_user(
            email='test@example.com',
            password='password123',
            first_name='John',
            last_name='Doe',
            phone='+2250707070707',
            user_type='LOUEUR'
        )
        self.assertEqual(user.email, 'test@example.com')
        self.assertTrue(user.check_password('password123'))
        self.assertEqual(user.get_full_name(), 'John Doe')
        self.assertEqual(user.user_type, 'LOUEUR')
        self.assertEqual(user.verification_status, 'documents_required')

    def test_create_superuser(self):
        admin = User.objects.create_superuser(
            email='admin@example.com',
            password='admin123'
        )
        self.assertEqual(admin.user_type, 'ADMIN')
        self.assertTrue(admin.is_verified)
        self.assertEqual(admin.verification_status, 'approved')

    def test_phone_validation(self):
        with self.assertRaises(ValidationError):
            user = User(
                email='test@example.com',
                phone='invalid',
                user_type='LOUEUR'
            )
            user.full_clean()

class ProprietaireProfileTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='proprio@example.com',
            password='test123',
            user_type='PROPRIETAIRE'
        )
        
    def test_profile_creation(self):
        profile = ProprietaireProfile.objects.create(
            user=self.user,
            cin='99X99999',
            address="123 Rue Test"
        )
        self.assertEqual(profile.__str__(), f"Profil Propriétaire - {self.user.email}")
        self.assertFalse(profile.documents_complets)
        
    def test_document_validation(self):
        profile = ProprietaireProfile(
            user=self.user,
            cin='99X99999',
            address="123 Rue Test"
        )
        
        # Test taille fichier
        large_file = SimpleUploadedFile("large.jpg", b"x" * 11*1024*1024)  # 11MB
        profile.assurance_document = large_file
        with self.assertRaises(ValidationError):
            profile.clean()

class VoitureModelTest(TestCase):
    def setUp(self):
        self.proprietaire = User.objects.create_user(
            email='proprio@example.com',
            password='test123',
            user_type='PROPRIETAIRE'
        )
        
    def test_voiture_creation(self):
        voiture = Voiture.objects.create(
            proprietaire=self.proprietaire,
            marque='Toyota',
            modele='Corolla',
            annee=2020,
            prix_jour=15000,
            ville='Abidjan'
        )
        self.assertEqual(voiture.__str__(), "Toyota Corolla (2020)")
        self.assertTrue(voiture.disponible)
        self.assertEqual(voiture.type_vehicule, 'berline')  # default
        
    def test_prix_validation(self):
        voiture = Voiture(
            proprietaire=self.proprietaire,
            marque='Toyota',
            modele='Corolla',
            annee=2020,
            prix_jour=999,  # < 1000
            ville='Abidjan'
        )
        with self.assertRaises(ValidationError):
            voiture.clean()

class ReservationModelTest(TestCase):
    def setUp(self):
        self.proprietaire = User.objects.create_user(
            email='proprio@example.com',
            password='test123',
            user_type='PROPRIETAIRE'
        )
        self.loueur = User.objects.create_user(
            email='loueur@example.com',
            password='test123',
            user_type='LOUEUR'
        )
        self.voiture = Voiture.objects.create(
            proprietaire=self.proprietaire,
            marque='Toyota',
            modele='Corolla',
            annee=2020,
            prix_jour=15000,
            ville='Abidjan'
        )
        
    def test_reservation_creation(self):
        reservation = Reservation.objects.create(
            voiture=self.voiture,
            client=self.loueur,
            date_debut=timezone.now().date(),
            date_fin=timezone.now().date() + timezone.timedelta(days=3),
            montant_paye=45000,
            statut='attente_paiement'
        )
        self.assertEqual(reservation.duree, 3)
        self.assertFalse(reservation.est_en_cours)
        
    def test_date_validation(self):
        reservation = Reservation(
            voiture=self.voiture,
            client=self.loueur,
            date_debut=timezone.now().date(),
            date_fin=timezone.now().date(),  # same date
            montant_paye=15000
        )
        with self.assertRaises(ValidationError):
            reservation.clean()

class PaiementModelTest(TestCase):
    def setUp(self):
        self.proprietaire = User.objects.create_user(
            email='proprio@example.com',
            password='test123',
            user_type='PROPRIETAIRE'
        )
        self.loueur = User.objects.create_user(
            email='loueur@example.com',
            password='test123',
            user_type='LOUEUR'
        )
        self.voiture = Voiture.objects.create(
            proprietaire=self.proprietaire,
            marque='Toyota',
            modele='Corolla',
            annee=2020,
            prix_jour=15000,
            ville='Abidjan'
        )
        self.reservation = Reservation.objects.create(
            voiture=self.voiture,
            client=self.loueur,
            date_debut=timezone.now().date(),
            date_fin=timezone.now().date() + timezone.timedelta(days=3),
            montant_paye=45000,
            statut='attente_paiement'
        )
        
    def test_paiement_creation(self):
        paiement = Paiement.objects.create(
            reservation=self.reservation,
            methode='ORANGE',
            montant=45000,
            statut='REUSSI'
        )
        self.assertEqual(paiement.__str__(), "Orange Money - 45000 XOF (Validé)")
        
    def test_currency_conversion(self):
        paiement = Paiement(
            reservation=self.reservation,
            methode='ORANGE',
            montant=100,
            devise_origine='USD',
            statut='EN_ATTENTE'
        )
        paiement.save()  # Devrait déclencher la conversion
        self.assertGreater(paiement.montant_converti, 50000)  # 1 USD > 500 XOF

class PortefeuilleModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='user@example.com',
            password='test123',
            user_type='LOUEUR'
        )
        
    def test_portefeuille_creation(self):
        portefeuille = Portefeuille.objects.create(
            proprietaire=self.user,
            solde=10000
        )
        self.assertEqual(portefeuille.__str__(), f"Portefeuille ({self.user.username})")
        
    def test_crediter(self):
        portefeuille = Portefeuille.objects.create(proprietaire=self.user)
        transaction = portefeuille.crediter(5000, "Dépôt initial")
        self.assertEqual(portefeuille.solde, 5000)
        self.assertEqual(transaction.type_transaction, 'depot')
        
    def test_debiter_solde_insuffisant(self):
        portefeuille = Portefeuille.objects.create(proprietaire=self.user, solde=1000)
        with self.assertRaises(ValueError):
            portefeuille.debiter(2000, "Retrait")
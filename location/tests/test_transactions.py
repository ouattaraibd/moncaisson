import os
from django.test import TestCase
from django.contrib.auth.models import Permission
from django.contrib.auth import get_user_model
from ..models import Portefeuille, Transaction

class TransactionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email='admin@example.com',
            username='admin',
            password='testpass',
            user_type='ADMIN'
        )
        permission = Permission.objects.get(codename='valider_transaction')
        self.user.user_permissions.add(permission)
        
        self.client_user = get_user_model().objects.create_user(
            username='client',
            email='test@example.com',
            password='testpass',
            user_type='LOUEUR'
        )
        self.portefeuille = Portefeuille.objects.create(
            proprietaire=self.client_user,
            solde=1000000
        )
        self.transaction = Transaction.objects.create(
            portefeuille=self.portefeuille,
            montant=50000,
            type_transaction='retrait',
            reference='TEST123'
        )

    def test_valider_retrait(self):
        self.client.login(username='admin', password='testpass')
        response = self.client.post(
            f'/portefeuille/transactions/{self.transaction.id}/valider/',
            {'action': 'valider'}
        )
        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.statut, 'valide')
        self.assertEqual(self.portefeuille.solde, 950000)

    def test_rejeter_retrait(self):
        self.client.login(username='admin', password='testpass')
        response = self.client.post(
            f'/portefeuille/transactions/{self.transaction.id}/valider/',
            {'action': 'rejeter', 'motif_rejet': 'Documentation manquante'}
        )
        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.statut, 'rejete')
        self.assertEqual(self.portefeuille.solde, 1000000)


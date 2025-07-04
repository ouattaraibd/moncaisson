# tests/test_user_manager.py
import os
from django.test import TestCase
from django.contrib.auth import get_user_model
from location.models.core_models import UserManager

User = get_user_model()

class UserManagerTest(TestCase):
    def test_create_user(self):
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password=os.getenv('TEST_PWD')
        )
        self.assertEqual(user.email, 'test@example.com')
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.is_active)

    def test_create_superuser(self):
        admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
        self.assertTrue(admin_user.is_superuser)
        self.assertTrue(admin_user.is_staff)
        self.assertEqual(admin_user.user_type, 'ADMIN')


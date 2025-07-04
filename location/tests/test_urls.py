# location/tests/test_urls.py
import os
from django.test import TestCase, Client
from django.urls import reverse

class UrlsTest(TestCase):
    def test_public_urls(self):
        client = Client()
        urls = [
            ('accueil', 200),
            ('connexion', 200),
            ('register_choice', 200),
            ('voitures', 200),
        ]
        
        for name, expected_status in urls:
            with self.subTest(url_name=name):
                response = client.get(reverse(name))
                self.assertEqual(response.status_code, expected_status)

    def test_protected_urls(self):
        client = Client()
        protected_urls = [
            'proprietaire_dashboard',
            'loueur_dashboard',
            'modifier_profil'
        ]
        
        for url_name in protected_urls:
            with self.subTest(url_name=url_name):
                response = client.get(reverse(url_name))
                self.assertEqual(response.status_code, 302)  # Redirection vers login


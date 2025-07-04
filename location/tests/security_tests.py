import os
from django.test import TestCase
from django.test.client import Client

class SecurityTests(TestCase):
    def test_waf_protection(self):
        tests = [
            ("/?test=<script>alert(1)</script>", 403),
            ("/?id=1' OR 1=1--", 403),
            ("/../../etc/passwd", 403)
        ]
        
        c = Client()
        for url, expected_status in tests:
            response = c.get(url)
            self.assertEqual(response.status_code, expected_status)
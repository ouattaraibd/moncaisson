# tests/test_cache.py
import os
from django.test import TestCase
from django.core.cache import cache

class CacheTest(TestCase):
    def test_cache_works(self):
        cache.set('test_key', 'test_value', 10)
        self.assertEqual(cache.get('test_key'), 'test_value')
        
    def test_cache_config(self):
        from django.conf import settings
        if not settings.TESTING:
            self.assertEqual(settings.CACHES['default']['BACKEND'], 
                           'django_redis.cache.RedisCache')


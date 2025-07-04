# tests/conftest.py
import os
from django.contrib.auth import get_user_model

def create_test_user(**kwargs):
    return get_user_model().objects.create_user(
        password=os.getenv('TEST_USER_PWD', 'fallback_secure_pwd_123!'),
        **kwargs
    )


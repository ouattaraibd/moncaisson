"""
Django settings for moncaisson project.
"""

import sys
from datetime import timedelta
from pathlib import Path
import os
from decouple import config, Csv
from django.urls import re_path
from django.views.static import serve

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent

# Test mode detection
TESTING = 'test' in sys.argv

LOG_DIR = os.path.join(BASE_DIR, 'logs')
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# Chargement des variables d'environnement
DEBUG = config('DEBUG', default=True, cast=bool)
SECRET_KEY = config('SECRET_KEY')
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='*', cast=Csv())

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs/dashboard_errors.log'),
            'formatter': 'verbose',
        },
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'debug_file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs/debug.log'),
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'ERROR',
            'propagate': True,
        },
        'location': {
            'handlers': ['console', 'debug_file'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
        'channels': {
            'handlers': ['console', 'debug_file'],
            'level': 'DEBUG' if DEBUG else 'INFO',
        },
        'django.file_uploads': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'DEBUG' if DEBUG else 'INFO',
    },
}

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'location.apps.LocationConfig',  # Configuration complète de l'app
    'django.contrib.auth',
    'axes',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    
    # Apps tiers
    'debug_toolbar' if not TESTING else None,
    'import_export',
    'django_ratelimit',
    'location.notifications',  # Sous-module
    'django_celery_results',
    'django_celery_beat',
    # 'location',  # À SUPPRIMER (déjà déclaré via location.apps.LocationConfig)
    # 'location.tasks',  # À SUPPRIMER (fait partie de location)
    'crispy_forms',
    'crispy_bootstrap5',
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'api',
    'channels',
]

INSTALLED_APPS = [app for app in INSTALLED_APPS if app is not None]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'axes.middleware.AxesMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'debug_toolbar.middleware.DebugToolbarMiddleware' if not TESTING else None,
    'location.middleware.AnalyticsMiddleware',
]

MIDDLEWARE = [mw for mw in MIDDLEWARE if mw is not None]

ROOT_URLCONF = 'moncaisson.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'templates'),
            os.path.join(BASE_DIR, 'location/templates'),
            os.path.join(BASE_DIR, 'templates/location/admin'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'debug': True,
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'location.context_processors.user_type',
                'location.context_processors.user_verification',
                'location.context_processors.dashboard_context',
            ],
            'string_if_invalid': 'INVALID_EXPRESSION: %s',
            'libraries': {
                'staticfiles': 'django.templatetags.static',
            },
        },
    },
]

ASGI_APPLICATION = 'moncaisson.asgi.application'
WSGI_APPLICATION = 'moncaisson.wsgi.application'

# Configuration Channels
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [(config('REDIS_HOST', default='127.0.0.1'), config('REDIS_PORT', default=6379, cast=int))],
            "capacity": 1500,
            "expiry": 10,
        },
    },
}

# Database
DATABASES = {
    'default': {
        'ENGINE': config('DB_ENGINE', default='django.db.backends.sqlite3'),
        'NAME': config('DB_NAME', default=BASE_DIR / 'db.sqlite3'),
        'USER': config('DB_USER', default=''),
        'PASSWORD': config('DB_PASSWORD', default=''),
        'HOST': config('DB_HOST', default=''),
        'PORT': config('DB_PORT', default=''),
        'TEST': {
            'NAME': BASE_DIR / 'test_db.sqlite3',
        },
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
        'OPTIONS': {
            'max_similarity': 0.7,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 10,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
    {
        'NAME': 'location.forms.CustomPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Africa/Abidjan'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'location/static'),
]

# Media files configuration
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# File upload settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
FILE_UPLOAD_PERMISSIONS = 0o644
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o755
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
DATA_UPLOAD_MAX_NUMBER_FIELDS = 1000

# Document verification settings
DOCUMENT_VERIFICATION_SETTINGS = {
    'MAX_FILE_SIZE': 10 * 1024 * 1024,  # 10MB
    'ALLOWED_TYPES': ['image/jpeg', 'image/png', 'application/pdf'],
    'REQUIRED_DOCS': {
        'PROPRIETAIRE': ['assurance_document', 'carte_grise_document'],
        'LOUEUR': ['driver_license', 'id_card'],
    }
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Cache configuration
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
            'IGNORE_EXCEPTIONS': True,
            'PICKLE_VERSION': -1
        },
        'KEY_PREFIX': 'moncaisson',
        'TIMEOUT': 300
    }
}

# Email
EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='webmaster@localhost')

# Debug Toolbar
INTERNAL_IPS = config('INTERNAL_IPS', default='127.0.0.1', cast=Csv())
DEBUG_TOOLBAR_CONFIG = {
    'SHOW_TOOLBAR_CALLBACK': lambda request: DEBUG and not TESTING,
    'IS_RUNNING_TESTS': TESTING,
}

# Authentication
AUTH_USER_MODEL = 'location.User'
LOGIN_URL = '/connexion/'
LOGIN_REDIRECT_URL = 'dashboard_redirect'
LOGOUT_REDIRECT_URL = 'accueil'

# Security
SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', default=False, cast=bool)
SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=False, cast=bool)
SESSION_COOKIE_AGE = config('SESSION_COOKIE_AGE', default=1209600, cast=int)
SESSION_SAVE_EVERY_REQUEST = config('SESSION_SAVE_EVERY_REQUEST', default=True, cast=bool)

# REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/day',
        'user': '1000/day'
    },
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser'
    ],
    'TEST_REQUEST_DEFAULT_FORMAT': 'json'
}

# CORS Settings
CORS_ALLOW_ALL_ORIGINS = config('CORS_ALLOW_ALL_ORIGINS', default=True, cast=bool)
CORS_ALLOW_CREDENTIALS = config('CORS_ALLOW_CREDENTIALS', default=True, cast=bool)
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

# Axes configuration
AXES_CACHE = 'default'
AXES_ENABLED = config('AXES_ENABLED', default=not DEBUG, cast=bool)
if TESTING:
    AXES_ENABLED = False

AXES_FAILURE_LIMIT = config('AXES_FAILURE_LIMIT', default=5, cast=int)
AXES_COOLOFF_TIME = config('AXES_COOLOFF_TIME', default=1, cast=int)
AXES_LOCKOUT_TEMPLATE = 'location/auth/lockout.html'
AXES_RESET_ON_SUCCESS = config('AXES_RESET_ON_SUCCESS', default=True, cast=bool)
AXES_HANDLER = 'axes.handlers.cache.AxesCacheHandler'
AXES_IPWARE_PROXY_ORDER = 'left-to-right'
AXES_IPWARE_PROXY_COUNT = 1
AXES_IPWARE_META_PRECEDENCE_ORDER = [
    'HTTP_X_FORWARDED_FOR',
    'REMOTE_ADDR',
]

# Django Ratelimit
RATELIMIT_USE_CACHE = 'default'
RATELIMIT_ENABLE = config('RATELIMIT_ENABLE', default=not DEBUG, cast=bool)

SILENCED_SYSTEM_CHECKS = [
    'django_ratelimit.E003',
    'django_ratelimit.W001',
    'axes.W002' if not DEBUG else None,
    'debug_toolbar.E001' if TESTING else None,
    'channels.E002',
]

SILENCED_SYSTEM_CHECKS = [check for check in SILENCED_SYSTEM_CHECKS if check is not None]

AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# CSRF
CSRF_COOKIE_SECURE = config('CSRF_COOKIE_SECURE', default=False, cast=bool)
CSRF_COOKIE_HTTPONLY = config('CSRF_COOKIE_HTTPONLY', default=False, cast=bool)
CSRF_USE_SESSIONS = config('CSRF_USE_SESSIONS', default=False, cast=bool)
CSRF_FAILURE_VIEW = 'django.views.csrf.csrf_failure'
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default='http://127.0.0.1:8000,http://localhost:8000', cast=Csv())

VERIFICATION_EXEMPT_URLS = [
    '/admin/',
    '/super-admin/',
    '/admin/login/',
    '/connexion/',
    '/deconnexion/',
    '/register/',
    '/accounts/',
    '/static/',
    '/media/',
    '/api/',
    '/__debug__/',
    '/ws/',
]

# Payment providers
ORANGE_MONEY_API_KEY = config('ORANGE_MONEY_API_KEY', default='')
ORANGE_MONEY_API_URL = config('ORANGE_MONEY_API_URL', default='https://api.orange.com/orange-money-webpay')
ORANGE_MONEY_MERCHANT_CODE = config('ORANGE_MONEY_MERCHANT_CODE', default='')

WAVE_API_KEY = config('WAVE_API_KEY', default='')
WAVE_API_URL = config('WAVE_API_URL', default='https://api.wave.com/v1')
WAVE_WEBHOOK_SECRET = config('WAVE_WEBHOOK_SECRET', default='')

PAYPAL_CLIENT_ID = config('PAYPAL_CLIENT_ID', default='')
PAYPAL_SECRET = config('PAYPAL_SECRET', default='')
PAYPAL_API_URL = config('PAYPAL_API_URL', default='https://api.sandbox.paypal.com')
PAYPAL_WEBHOOK_ID = config('PAYPAL_WEBHOOK_ID', default='')

STRIPE_API_KEY = config('STRIPE_API_KEY', default='')
STRIPE_PUBLIC_KEY = config('STRIPE_PUBLIC_KEY', default='')
STRIPE_WEBHOOK_SECRET = config('STRIPE_WEBHOOK_SECRET', default='')
STRIPE_SECRET_KEY = config('STRIPE_SECRET_KEY', default='')
STRIPE_SECRET_KEY_CI = config('STRIPE_SECRET_KEY_CI', default='')

# xhtml2pdf config
XHTML2PDF_DEFAULT_FONT = os.path.join(BASE_DIR, 'static', 'location', 'fonts', 'DejaVuSans.ttf')
XHTML2PDF_ENCODING = 'utf-8'

# Celery Configuration
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/1'
CELERY_TIMEZONE = 'Africa/Abidjan'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
CELERY_BEAT_SCHEDULE = {
    'check-pending-payments': {
        'task': 'location.tasks.payment_tasks.check_pending_payments',
        'schedule': 1800.0,  # Toutes les 30 minutes
    },
    'send-message-notifications': {
        'task': 'location.tasks.messaging_tasks.send_message_notification',
        'schedule': 60.0,  # Toutes les minutes
    },
}

# Configuration supplémentaire recommandée
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes max par tâche
CELERY_RESULT_EXPIRES = 86400  # Résultats conservés 24h

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

SITE_URL = config('SITE_URL', default='http://127.0.0.1:8000')

# Ajouter dans SECURITY SECTION
SECURE_HSTS_SECONDS = 30 * 24 * 60 * 60  # 30 jours
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# Configuration PWA
PWA_APP_NAME = 'MonCaisson'
PWA_APP_DESCRIPTION = "Location de voitures en Côte d'Ivoire"
PWA_APP_THEME_COLOR = '#fd7e14'
PWA_APP_BACKGROUND_COLOR = '#ffffff'
PWA_APP_DISPLAY = 'standalone'
PWA_APP_SCOPE = '/'
PWA_APP_ORIENTATION = 'portrait'
PWA_APP_START_URL = '/'
PWA_APP_ICONS = [
    {
        'src': '/static/location/images/logo-192x192.png',
        'sizes': '192x192'
    }
]

ADMIN_NOTIFICATIONS = True 
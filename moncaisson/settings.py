"""
Django settings for moncaisson project - Configuration de production sécurisée
"""

import sys
import os
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse
from cryptography.fernet import Fernet, InvalidToken
from django.utils.http import http_date
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from decouple import config, Csv



# Chargement des variables d'environnement
from dotenv import load_dotenv
load_dotenv()

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent

REQUEST_TIMEOUT = 10  # seconds
GLOBAL_TIMEOUT = 10  # Timeout global pour toutes les requêtes externes

# 1. Initialisation du chiffrement ============================================

ENCRYPTION_KEY = config('ENCRYPTION_KEY')

def get_encrypted_password(env_var_name, default=None):
    """Déchiffre les mots de passe stockés chiffrés"""
    try:
        cipher_suite = Fernet(ENCRYPTION_KEY.encode())
        encrypted_pwd = config(env_var_name, default='')
        
        if not encrypted_pwd:
            if default is not None:
                return default
            raise ValueError(f"La variable {env_var_name} est vide")
            
        return cipher_suite.decrypt(encrypted_pwd.encode()).decode()
        
    except InvalidToken:
        if DEBUG:
            print(f"Attention: Échec du déchiffrement pour {env_var_name}")
            return "password_insecure_in_dev" if default is None else default
        raise
    except Exception as e:
        if DEBUG:
            print(f"Erreur de déchiffrement pour {env_var_name}: {str(e)}")
            return "password_insecure_in_dev" if default is None else default
        raise ValueError(f"Erreur de déchiffrement pour {env_var_name}: {str(e)}")

# 2. CONFIGURATION DE BASE ====================================================

# Sécurité : Validation des variables requises
REQUIRED_ENV_VARS = ['SECRET_KEY', 'DB_NAME', 'DB_USER', 'DB_PASSWORD', 'REDIS_PASSWORD', 'ENCRYPTION_KEY']
missing_vars = [var for var in REQUIRED_ENV_VARS if not config(var, default='')]
if missing_vars:
    raise RuntimeError(f"Variables manquantes dans .env: {', '.join(missing_vars)}")

# Mode debug - Désactivé en production
DEBUG = True
TESTING = 'test' in sys.argv

# Clé secrète et hôtes autorisés
SECRET_KEY = config('SECRET_KEY')
ALLOWED_HOSTS = config('ALLOWED_HOSTS', cast=Csv())

# 3. CONFIGURATION DE SÉCURITÉ ================================================

# Protection contre les attaques
SECURE_HSTS_SECONDS = 31_536_000  # 1 an
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_SSL_REDIRECT = False
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'
SECURE_CROSS_ORIGIN_EMBEDDER_POLICY = 'require-corp'
SECURE_FLOC = False 
SECURE_REFERRER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'

# Cookies sécurisés
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
CSRF_USE_SESSIONS = True
CSRF_COOKIE_HTTPONLY = True
CSRF_FAILURE_VIEW = 'location.views.errors.csrf_failure'
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 1209600  # 2 semaines en secondes
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_SAVE_EVERY_REQUEST = True
HANDLER404 = 'location.views.errors.handler404'
HANDLER500 = 'location.views.errors.handler500'
CSRF_TRUSTED_ORIGINS = [
    'https://127.0.0.1:8000',
    'https://localhost:8000'
]


# Content Security Policy


# 4. APPLICATIONS ET MIDDLEWARE ===============================================

INSTALLED_APPS = [
    # Django core
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    
    # Third-party
    'corsheaders',
    'crispy_forms',
    'crispy_bootstrap5',
    'rest_framework',
    'rest_framework.authtoken',
    'rest_framework_simplejwt',
    'channels',
    'axes',
    'debug_toolbar',
    'sslserver',
    'import_export',
    'django_ratelimit',
    'django_celery_results',
    'django_celery_beat',
    'django_extensions',
    'honeypot',
    
    # Local apps
    'location.apps.LocationConfig',
    'api.apps.ApiConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    #'moncaisson.waf_middleware.WAFMiddleware',
    'honeypot.middleware.HoneypotMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    #'moncaisson.waf_scoring.IPScoringMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    #'debug_toolbar.middleware.DebugToolbarMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'axes.middleware.AxesMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

if DEBUG and not TESTING:
    MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')  # Ajout au début
    INTERNAL_IPS = ['127.0.0.1']

# 5. BASE DE DONNÉES =========================================================

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': get_encrypted_password('DB_PASSWORD'),  # Utilisez la fonction de déchiffrement
        'HOST': config('DB_HOST'),
        'PORT': config('DB_PORT'),
        'OPTIONS': {
            'client_encoding': 'UTF8',
        }
    }
}

# 6. AUTHENTIFICATION ========================================================

AUTH_USER_MODEL = 'location.User'
AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
]

LOGIN_URL = '/connexion/'
LOGIN_REDIRECT_URL = 'dashboard_redirect'
LOGOUT_REDIRECT_URL = 'accueil'

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
        'OPTIONS': {
            'max_similarity': 0.5,
            'user_attributes': ('username', 'email', 'first_name', 'last_name')
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 14,
        }
    },
    
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.UppercaseValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.LowercaseValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.SymbolValidator',
    },
    {
        'NAME': 'location.validators.UppercaseValidator',
    },
]

# Configuration Axes (protection contre les attaques par force brute)
AXES_ENABLED = not DEBUG
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=30)
AXES_LOCKOUT_PARAMETERS = [["ip_address", "user_agent", "username"]]
AXES_HANDLER = 'axes.handlers.cache.AxesCacheHandler'
AXES_LOCKOUT_TEMPLATE = 'account/locked.html'
AXES_RESET_ON_SUCCESS = True


# 7. INTERNATIONALISATION ====================================================

LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Africa/Abidjan'
USE_I18N = True
USE_L10N = True
USE_TZ = True

# 8. FICHIERS STATIQUES =====================================================

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
WHITENOISE_MAX_AGE = 31536000  # 1 an

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
FILE_UPLOAD_PERMISSIONS = 0o644
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o755
FILE_UPLOAD_HANDLERS = [
    'django.core.files.uploadhandler.TemporaryFileUploadHandler',
]
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
DATA_UPLOAD_MAX_NUMBER_FIELDS = 1000

# 9. EMAIL ===================================================================

EMAIL_BACKEND = config('EMAIL_BACKEND')
EMAIL_HOST = config('EMAIL_HOST')
EMAIL_PORT = config('EMAIL_PORT', cast=int)
EMAIL_HOST_USER = config('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = get_encrypted_password('EMAIL_HOST_PASSWORD')
EMAIL_USE_TLS = config('EMAIL_USE_TLS', cast=bool)
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL')

# 10. CELERY ==================================================================

CELERY_BROKER_URL = f'redis://:{get_encrypted_password("REDIS_PASSWORD")}@{config("REDIS_HOST")}:{config("REDIS_PORT")}/0'
CELERY_RESULT_BACKEND = f'redis://:{get_encrypted_password("REDIS_PASSWORD")}@{config("REDIS_HOST")}:{config("REDIS_PORT")}/1'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
CELERY_TASK_SOFT_TIME_LIMIT = 20 * 60  # 20 minutes
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
CELERY_TASK_ANNOTATIONS = {
    '*': {
        'rate_limit': '10/m',
        'max_retries': 3,
        'default_retry_delay': 60,
    }
}

# 11. REST FRAMEWORK =========================================================

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/day',
        'user': '1000/day',
        'burst': '60/min',
        'sustained': '1000/day'
    },
    'COERCE_DECIMAL_TO_STRING': False,
    'DEFAULT_SCHEMA_CLASS': 'rest_framework.schemas.coreapi.AutoSchema',
    'UNAUTHENTICATED_USER': None,
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
}

# 12. SENTRY (MONITORING) ====================================================

if not DEBUG and config('SENTRY_DSN', default=''):
    sentry_sdk.init(
        dsn=config('SENTRY_DSN'),
        integrations=[DjangoIntegration()],
        traces_sample_rate=1.0,
        send_default_pii=True,
        environment=config('ENV', 'production')
    )

# 13. LOGGING ================================================================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'waf_file': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'logs/waf.log'),
            'maxBytes': 5*1024*1024,  # 5MB
            'backupCount': 3,
            'formatter': 'verbose',
            'delay': True,  # Important pour Windows
        },
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler',
            'include_html': True,
        },
    },
    'loggers': {
        'moncaisson.waf_middleware': {
            'handlers': ['waf_file', 'mail_admins'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django': {
            'handlers': ['waf_file'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}

# 13. Configuration des canaux ==============================================

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [(config('REDIS_HOST'), config('REDIS_PORT', cast=int))],
            "password": get_encrypted_password('REDIS_PASSWORD'),
        },
    },
}

# 14. CONFIGURATION DES PAIEMENTS ============================================

# Stripe
STRIPE_API_KEY = get_encrypted_password('STRIPE_API_KEY')
STRIPE_WEBHOOK_SECRET = get_encrypted_password('STRIPE_WEBHOOK_SECRET')

# PayPal
PAYPAL_CLIENT_ID = get_encrypted_password('PAYPAL_CLIENT_ID', default='')  # Valeur vide par défaut
PAYPAL_SECRET = get_encrypted_password('PAYPAL_SECRET', default='')

# Orange Money
ORANGE_MONEY_API_KEY = get_encrypted_password('ORANGE_MONEY_API_KEY')
ORANGE_MONEY_MERCHANT_CODE = get_encrypted_password('ORANGE_MONEY_MERCHANT_CODE')

# 15. CONFIGURATION DES TEMPLATES ============================================

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'templates'),
            os.path.join(BASE_DIR, 'moncaisson/location/templates'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'location.context_processors.user_type',
            ],
        },
    },
]

# 16. AUTRES PARAMÈTRES =====================================================

# CORS
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', cast=Csv())
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = [
    'GET',
    'POST',
    'PUT',
    'PATCH',
    'DELETE',
    'OPTIONS'
]
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]
CORS_EXPOSE_HEADERS = []
CORS_PREFLIGHT_MAX_AGE = 86400

# Fichiers upload
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
FILE_UPLOAD_PERMISSIONS = 0o644
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB

# Configuration Channels
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [(config('REDIS_HOST'), config('REDIS_PORT', cast=int))],
            "password": get_encrypted_password('REDIS_PASSWORD'),
        },
    },
}

# Configuration PWA
PWA_APP_NAME = 'MonCaisson'
PWA_APP_DESCRIPTION = "Location de voitures en Côte d'Ivoire"
PWA_APP_THEME_COLOR = '#fd7e14'
PWA_APP_BACKGROUND_COLOR = '#ffffff'

# Configuration supplémentaire ==============================================

ROOT_URLCONF = 'moncaisson.urls'
WSGI_APPLICATION = 'moncaisson.wsgi.application'
ASGI_APPLICATION = 'moncaisson.asgi.application'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REQUEST_TIMEOUTS = {
    'DEFAULT': 10,
    'CINETPAY': 15,
    'STRIPE': 8,
    'PAYPAL': 12
}

#redis

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f'redis://:{get_encrypted_password("REDIS_PASSWORD")}@{config("REDIS_HOST")}:{config("REDIS_PORT")}/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'SERIALIZER': 'django_redis.serializers.json.JSONSerializer',
            'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
            'IGNORE_EXCEPTIONS': True,
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
        },
        'KEY_PREFIX': 'moncaisson',
        'TIMEOUT': 60 * 15,  # 15 minutes
    },
    'axes_cache': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f'redis://:{get_encrypted_password("REDIS_PASSWORD")}@{config("REDIS_HOST")}:{config("REDIS_PORT")}/2',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

AXES_CACHE = 'axes_cache'

LOGGING['handlers']['slack'] = {
    'level': 'CRITICAL',
    'class': 'django_slack.log.SlackExceptionHandler',
    'formatter': 'verbose',
    'token': config('SLACK_TOKEN', default=''),
    'channel': '#security-alerts',
}

LOGGING['loggers']['django.security'] = {
    'handlers': ['waf_file', 'mail_admins', 'slack'],
    'level': 'WARNING',
    'propagate': False,
}

MIDDLEWARE.insert(1, 'django.middleware.common.CommonMiddleware')

# Configuration Honeypot
HONEYPOT_DELAY = True  # Active les délais aléatoires
HONEYPOT_LOG_LEVEL = 'INFO'  # Niveau de log
HONEYPOT_TRAP_PATHS = [
    '/wp-admin/',
    '/wp-login.php',
    '/admin/login/',
    '/hidden-admin/',
    '/.env',
    '/config.php'
]
HONEYPOT_THRESHOLD = 5  # Nombre de tentatives avant blocage
HONEYPOT_BLOCK_TIMEOUT = 86400  # 24 heures en secondes
HONEYPOT_ENABLE_SYSTEM_BLOCK = False  # Active le blocage au niveau du système
HONEYPOT_FIELD_NAME = 'email2'  # Champ piège pour les bots
HONEYPOT_VERIFY_VALUE = '123'   # Valeur attendue

# WAF Configuration
WAF_ENABLED = False  # Peut être désactivé globalement
DISABLE_WAF = True  # Surcharge pour désactiver complètement

# Pour développement local seulement
if DEBUG:
    DISABLE_WAF = True
    WAF_ENABLED = False
    
RUNSERVER_PLUS_POLLER_RELOADER = False
RUNSERVER_PLUS_POLLER_RELOADER_INTERVAL = 2
RUNSERVER_PLUS_POLLER_RELOADER_TYPE = 'watchdog' 

if DEBUG:
    CSRF_COOKIE_SECURE = False  # Autoriser HTTP pour le dev
    SESSION_COOKIE_SECURE = False
    SECURE_SSL_REDIRECT = False
else:
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
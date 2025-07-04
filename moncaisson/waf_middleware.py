import re
import logging
from django.http import HttpResponseForbidden
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)

class WAFMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # Règles allégées pour le développement
        self.rules = [
            # Seules les règles critiques restent activées
            (r'UNION.*SELECT', 'SQL Injection'),
            (r'exec\(', 'Command Injection'),
            (r'DROP TABLE', 'SQL Injection'),
            (r'benchmark\s*\(', 'SQL Timing Attack'),
        ]
        
        # Chemins exemptés
        self.EXEMPT_PATHS = [
            '/', 
            '/static/*', 
            '/media/*',
            '/admin/*',
            '/favicon.ico',
            '/connexion/'  # Ajout spécifique pour la page de connexion
        ]
        
        # Headers à ignorer
        self.SAFE_HEADERS = [
            'HTTP_USER_AGENT',
            'HTTP_ACCEPT',
            'HTTP_ACCEPT_LANGUAGE',
            'HTTP_ACCEPT_ENCODING',
            'HTTP_CONNECTION',
            'HTTP_CACHE_CONTROL',
            'PATH',
            'SYSTEMROOT',
            'SERVER_SOFTWARE'
        ]

    def __call__(self, request):
        # Désactivation conditionnelle du WAF
        if getattr(settings, 'DISABLE_WAF', False) or settings.DEBUG:
            return self.get_response(request)
            
        # Vérification des chemins exemptés
        if any(request.path.startswith(path.replace('*', '')) for path in self.EXEMPT_PATHS):
            return self.get_response(request)

        client_ip = self._get_client_ip(request)
        if cache.get(f'blocked_ip_{client_ip}'):
            logger.warning(f"IP bloquée temporairement : {client_ip}")
            return HttpResponseForbidden("Accès temporairement bloqué")

        # Vérification des paramètres GET/POST
        for param, value in {**request.GET, **request.POST}.items():
            if self._check_param(str(value), request):
                self._log_attack(request, client_ip, param, value)
                return HttpResponseForbidden("Requête bloquée - Activité suspecte détectée")

        # Vérification des headers (plus permissive)
        for header, value in request.META.items():
            if header in self.SAFE_HEADERS:
                continue
                
            if self._check_param(str(value), request):
                self._log_attack(request, client_ip, f"Header:{header}", value)
                return HttpResponseForbidden("Requête bloquée - Header suspect")

        return self.get_response(request)

    def _check_param(self, value, request):
        """Version allégée de la vérification"""
        str_value = str(value).lower()
        return any(re.search(pattern, str_value) for pattern, _ in self.rules)

    def _log_attack(self, request, ip, param, value):
        """Journalisation moins verbose"""
        logger.warning(
            f"WAF Alert - IP:{ip} | "
            f"Path:{request.path} | "
            f"Param:{param} | "
            f"Value:{str(value)[:100]}"
        )
        cache.set(f'blocked_ip_{ip}', True, timeout=300)  # 5 minutes de blocage

    def _get_client_ip(self, request):
        """Simplifié pour le développement"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')
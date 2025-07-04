from django.http import HttpResponseForbidden
from django.core.cache import cache
from .models import LoginAttempt, BlockedIP
from django.conf import settings
from django.utils import timezone
import logging
import subprocess
import platform

logger = logging.getLogger(__name__)

class HoneypotMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.trap_paths = getattr(settings, 'HONEYPOT_TRAP_PATHS', [
            '/wp-admin/',
            '/wp-login.php', 
            '/admin/login/',
            '/hidden-admin/',
            '/.env',
            '/config.php'
        ])
        self.threshold = getattr(settings, 'HONEYPOT_THRESHOLD', 5)
        self.block_timeout = getattr(settings, 'HONEYPOT_BLOCK_TIMEOUT', 3600)
        self.enable_system_block = getattr(settings, 'HONEYPOT_ENABLE_SYSTEM_BLOCK', False)

    def _block_ip_system(self, ip):
        """Méthode interne pour bloquer les IPs"""
        try:
            if platform.system() == 'Windows':
                result = subprocess.run(
                    f'netsh advfirewall firewall add rule name="BLOCK {ip}" dir=in action=block remoteip={ip}',
                    shell=True,
                    check=True,
                    capture_output=True,
                    text=True
                )
                logger.info(f"IP {ip} bloquée dans le firewall Windows")
                return True
            else:
                logger.warning("Blocage système non disponible sur ce OS")
                return False
        except subprocess.CalledProcessError as e:
            logger.error(f"Erreur blocage IP {ip}: {e.stderr}")
            return False

    def __call__(self, request):
        if any(trap in request.path for trap in self.trap_paths):
            ip = self._get_client_ip(request)
            if not ip:
                return self.get_response(request)

            if cache.get(f'honeypot_block_{ip}'):
                return HttpResponseForbidden("Accès bloqué")

            if BlockedIP.objects.filter(ip_address=ip).exists():
                return HttpResponseForbidden("Accès bloqué")
            
            attempt_count = LoginAttempt.objects.filter(
                ip_address=ip,
                timestamp__gte=timezone.now()-timezone.timedelta(hours=1)
            ).count()
            
            if attempt_count >= self.threshold:
                cache.set(f'honeypot_block_{ip}', True, timeout=self.block_timeout)
                BlockedIP.objects.get_or_create(ip_address=ip)
                
                if self.enable_system_block:
                    self._block_ip_system(ip)
                
                return HttpResponseForbidden("Trop de tentatives")

        return self.get_response(request)

    def _get_client_ip(self, request):
        """Récupère l'IP client de manière sécurisée"""
        try:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                return x_forwarded_for.split(',')[0].strip()
            return request.META.get('REMOTE_ADDR', '')
        except Exception as e:
            logger.error(f"Erreur récupération IP: {str(e)}")
            return None
from django.apps import apps
from django.db import transaction
from threading import local
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from django.utils.deprecation import MiddlewareMixin
import logging

logger = logging.getLogger(__name__)

_thread_locals = local()

class AnalyticsMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        """
        Middleware pour le tracking des pages vues
        Version sécurisée avec gestion d'erreur complète
        """
        # Exclusion des URLs non pertinentes
        excluded_paths = [
            '/admin/',
            '/api/',
            '/static/',
            '/media/',
            '/favicon.ico'
        ]
        
        if not any(request.path.startswith(path) for path in excluded_paths):
            self._track_page_view(request, response.status_code)
        
        return response

    def _track_page_view(self, request, status_code):
        """
        Méthode de tracking sécurisée avec vérifications
        """
        try:
            # Vérification que les apps sont prêtes
            if not apps.ready:
                return
            
            # Vérification que le modèle est disponible
            if not apps.is_installed('location'):
                return
                
            # Import différé du modèle
            PageView = apps.get_model('location', 'PageView')
        
            # Données de base
            tracking_data = {
                'url': request.path[:255],
                'user': request.user if request.user.is_authenticated else None,
                'ip_address': self._get_client_ip(request) or '',
                'referrer': request.META.get('HTTP_REFERER', '')[:255],
                'method': request.method,
                'status_code': status_code if hasattr(PageView, 'status_code') else None
            }
        
            # Supprime les champs None si le modèle ne les supporte pas
            if not hasattr(PageView, 'status_code'):
                tracking_data.pop('status_code')
        
            PageView.objects.create(**tracking_data)
        
        except Exception as e:
            logger.error(f"Tracking error: {str(e)}", exc_info=True)

    def _get_client_ip(self, request):
        """
        Récupération sécurisée de l'IP client
        """
        try:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                return x_forwarded_for.split(',')[0].strip()
            return request.META.get('REMOTE_ADDR', '')
        except Exception:
            return ''
        
class UserTypeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # Redirige les propriétaires qui essaient d'accéder au dashboard loueur
            if (request.path.startswith('/dashboard/loueur/') 
                and hasattr(request.user, 'proprietaire_profile')):
                return redirect('proprietaire_dashboard')
        
        return self.get_response(request)
        
class FraudDetectionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if request.user.is_authenticated:
            check_suspicious_activity(request.user)
        return self.get_response(request)
        
class VerificationMiddleware(MiddlewareMixin):
    def __init__(self, get_response):
        self.get_response = get_response
        # Liste étendue des URLs exemptées
        self.exempt_urls = [
            '/admin/',
            '/admin/login/',
            '/super-admin/',
            '/connexion/',
            '/deconnexion/',
            '/register/',
            '/accounts/',
            '/static/',
            '/media/',
            '/api/',
            '/verification/',  # URL de vérification
            '/dashboard/redirect/',
            '/__debug__/',
            '/policies/accept/',
            '/favicon.ico',
            '/facture/',
            '/webhooks/'
        ]

    def __call__(self, request):
        path = request.path
        
        # 1. URLs exemptées
        if any(path.startswith(url) for url in self.exempt_urls):
            return self.get_response(request)
            
        # 2. Bypass si non authentifié
        if not request.user.is_authenticated:
            return self.get_response(request)
            
        # 3. Bypass pour staff/superuser
        if request.user.is_staff or request.user.is_superuser:
            return self.get_response(request)
            
        # 4. Vérification simplifiée pour éviter les boucles
        if not self.is_minimally_verified(request.user):
            if path != reverse('upload_verification'):
                return redirect('upload_verification')
                
        return self.get_response(request)

    def is_minimally_verified(self, user):
        """Vérification minimale pour éviter les boucles"""
        return getattr(user, 'is_verified', False)

    def is_fully_verified(self, user):
        """Version simplifiée pour éviter les blocages"""
        if not getattr(user, 'is_verified', False):
            return False
            
        if user.user_type == 'PROPRIETAIRE':
            return hasattr(user, 'proprietaire_profile')  # On ne vérifie plus les documents
            
        return True  # Pour les autres types d'utilisateurs

    # Méthodes utilitaires existantes conservées
    def _track_page_view(self, request, status_code):
        """Méthode de tracking sécurisée avec vérifications"""
        try:
            if not apps.ready or not apps.is_installed('location'):
                return
                
            PageView = apps.get_model('location', 'PageView')
            tracking_data = {
                'url': request.path[:255],
                'user': request.user if request.user.is_authenticated else None,
                'ip_address': self._get_client_ip(request) or '',
                'referrer': request.META.get('HTTP_REFERER', '')[:255],
                'method': request.method,
                'status_code': status_code if hasattr(PageView, 'status_code') else None
            }
            
            if not hasattr(PageView, 'status_code'):
                tracking_data.pop('status_code')
            
            PageView.objects.create(**tracking_data)
            
        except Exception as e:
            logger.error(f"Tracking error: {str(e)}", exc_info=True)

    def _get_client_ip(self, request):
        """Récupération sécurisée de l'IP client"""
        try:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                return x_forwarded_for.split(',')[0].strip()
            return request.META.get('REMOTE_ADDR', '')
        except Exception:
            return ''
        
class AdminAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.admin_paths = ['/admin-dashboard/', '/admin-validate/']

    def __call__(self, request):
        if any(request.path.startswith(path) for path in self.admin_paths):
            if not request.user.is_authenticated or not request.user.is_staff:
                return redirect('/admin/login/?next=' + request.path)
        return self.get_response(request)


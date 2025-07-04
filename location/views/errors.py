from django.shortcuts import render
from django.views.decorators.csrf import requires_csrf_token
from django.views.decorators.http import require_GET
from django.template import RequestContext
import logging

logger = logging.getLogger(__name__)

@requires_csrf_token
def csrf_failure(request, reason=""):
    logger.warning(
        f"Échec CSRF - IP: {request.META.get('REMOTE_ADDR')} | "
        f"User: {request.user if request.user.is_authenticated else 'Anonyme'} | "
        f"Path: {request.path} | "
        f"Method: {request.method} | "
        f"Reason: {reason}"
    )
    
    context = {
        'reason': reason,
        'request_path': request.path,
        'page_title': "Erreur de sécurité"
    }
    return render(request, 'location/errors/csrf_failure.html', context, status=403)

@require_GET
def handler404(request, exception):
    """Gestion personnalisée des erreurs 404"""
    logger.error(f"Page non trouvée: {request.path}")
    return render(request, 'location/errors/404.html', status=404)

@require_GET
def handler500(request):
    """Gestion personnalisée des erreurs 500"""
    logger.critical("Erreur serveur interne")
    return render(request, 'location/errors/500.html', status=500)
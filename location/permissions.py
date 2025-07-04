from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import user_passes_test
from rest_framework import permissions

def check_proprietaire(user):
    if not user.is_authenticated or user.user_type != 'PROPRIETAIRE':
        raise PermissionDenied("Accès réservé aux propriétaires")
    if not user.is_verified:
        raise PermissionDenied("Vérification d'identité requise")
    return True

def check_loueur(user):
    if not user.is_authenticated or user.user_type != 'LOUEUR':
        raise PermissionDenied("Accès réservé aux loueurs")
    return True

proprietaire_required = user_passes_test(check_proprietaire, login_url='connexion')
loueur_required = user_passes_test(check_loueur, login_url='connexion')

class ProprietaireRequiredMixin:
    """Mixin pour restreindre l'accès aux propriétaires"""
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise PermissionDenied("Veuillez vous connecter")
        if request.user.user_type != 'PROPRIETAIRE':
            raise PermissionDenied("Réservé aux propriétaires de voitures")
        return super().dispatch(request, *args, **kwargs)

class LoueurRequiredMixin:
    """Mixin pour restreindre l'accès aux loueurs"""
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise PermissionDenied("Veuillez vous connecter")
        if request.user.user_type != 'LOUEUR':
            raise PermissionDenied("Réservé aux locataires de voitures")
        return super().dispatch(request, *args, **kwargs)

# Décorateurs pratiques
def proprietaire_required(view_func):
    """Décorateur pour les vues réservées aux propriétaires"""
    actual_decorator = user_passes_test(
        lambda u: u.is_authenticated and u.user_type == 'PROPRIETAIRE',
        login_url='/connexion/',
        redirect_field_name=None
    )
    return actual_decorator(view_func)

def loueur_required(view_func):
    """Décorateur pour les vues réservées aux loueurs"""
    actual_decorator = user_passes_test(
        lambda u: u.is_authenticated and u.user_type == 'LOUEUR',
        login_url='/connexion/',
        redirect_field_name=None
    )
    return actual_decorator(view_func)
    
class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Permission personnalisée pour n'autoriser que le propriétaire d'un objet ou un admin
    """
    def has_object_permission(self, request, view, obj):
        # L'admin a toujours accès
        if request.user and request.user.is_staff:
            return True
        
        # Vérifie si l'utilisateur est propriétaire
        # Adaptez cette logique selon votre modèle DeliveryRequest
        if hasattr(obj, 'reservation'):
            return obj.reservation.client == request.user
        elif hasattr(obj, 'client'):
            return obj.client == request.user
        elif hasattr(obj, 'user'):
            return obj.user == request.user
        
        return False


from django.conf import settings

def user_type(request):
    """Fournit les variables de type d'utilisateur dans tous les templates"""
    return {
        'is_loueur': request.user.is_authenticated and getattr(request.user, 'user_type', None) == 'LOUEUR',
        'is_proprietaire': request.user.is_authenticated and getattr(request.user, 'user_type', None) == 'PROPRIETAIRE',
        'is_admin': request.user.is_authenticated and request.user.is_staff,
    }

def user_verification(request):
    """Fournit le statut de vérification de l'utilisateur"""
    if not request.user.is_authenticated:
        return {}
    
    return {
        'user_is_verified': getattr(request.user, 'is_verified', False),
        'verification_status': getattr(
            getattr(request.user, 'verification', None), 
            'status', 
            None
        ),
        'verification_pending': hasattr(request.user, 'verification') and 
                              getattr(request.user.verification, 'status', None) == 'en_attente',
    }

def dashboard_context(request):
    """Contexte global pour les tableaux de bord"""
    context = {}
    if request.user.is_authenticated:
        base_context = {
            'user_photo': request.user.photo.url if hasattr(request.user, 'photo') and request.user.photo else None,
            'user_full_name': request.user.get_full_name() or request.user.username,
        }
        
        if getattr(request.user, 'user_type', None) == 'PROPRIETAIRE':
            context.update({
                **base_context,
                'has_voitures': hasattr(request.user, 'voitures') and request.user.voitures.exists(),
            })
        elif getattr(request.user, 'user_type', None) == 'LOUEUR':
            context.update({
                **base_context,
                'has_reservations': hasattr(request.user, 'reservations_client') and request.user.reservations_client.exists(),
            })
    
    return context
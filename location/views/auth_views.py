from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, load_backend, authenticate
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from location.models.loyalty_models import LoyaltyProfile
from axes.decorators import axes_dispatch
from django_ratelimit.decorators import ratelimit
from django.contrib.auth.views import LoginView
from django.contrib.auth.forms import AuthenticationForm
from location.models import Voiture, User, Reservation
from decimal import Decimal
from django.db import transaction
from django.utils.http import url_has_allowed_host_and_scheme
from location.models.core_models import ProprietaireProfile, Document, DocumentVerification
from django.conf import settings
from axes.helpers import get_lockout_response
from django.views.decorators.csrf import csrf_protect 
from location.forms import ProprietaireSignUpForm, LoueurSignUpForm, ProfilForm, ProprietaireDocumentsForm
from .dashboard_views import loueur_dashboard, proprietaire_dashboard
import logging

logger = logging.getLogger(__name__)


@require_http_methods(["GET"])
def accueil(request):
    voitures = Voiture.objects.all()
    return render(request, 'location/accueil.html', {'voitures': voitures})

@ratelimit(key='ip', rate='3/h', block=True)
@axes_dispatch
@csrf_protect 
@never_cache
@require_http_methods(["GET", "POST"])
def connexion(request):
    if request.user.is_authenticated:
        if request.user.is_superuser:
            return redirect('admin_dashboard')
        elif request.user.user_type == 'PROPRIETAIRE':
            return redirect('proprietaire_dashboard')
        return redirect('loueur_dashboard')
    
    next_url = request.GET.get('next', '')
    
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, "Connexion réussie !")
            
            next_url = request.POST.get('next', '')
            if next_url and url_has_allowed_host_and_scheme(
                url=next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure()
            ):
                return redirect(next_url)
                
            if user.is_superuser:
                return redirect('admin_dashboard')
            elif user.user_type == 'PROPRIETAIRE':
                return redirect('proprietaire_dashboard')
            return redirect('loueur_dashboard')
    else:
        form = AuthenticationForm()
    
    return render(request, 'location/connexion.html', {
        'form': form,
        'next': next_url
    })

@never_cache
@require_http_methods(["POST"])
def deconnexion(request):
    logout(request)
    messages.info(request, "Vous avez été déconnecté")
    return redirect('accueil')

@never_cache
@require_http_methods(["GET"])
def register_choice(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'location/auth/register_choice.html')

@never_cache
@require_http_methods(["GET", "POST"])
@transaction.atomic
def register_proprietaire(request):
    """
    Vue d'inscription optimisée pour les propriétaires avec :
    - Gestion transactionnelle atomique
    - Upload et vérification des documents
    - Logging complet
    - Notifications admin
    - Redirection intelligente
    """
    
    # Redirection si déjà authentifié
    if request.user.is_authenticated:
        messages.info(request, "Vous êtes déjà connecté.")
        return redirect('dashboard_redirect')

    if request.method == 'POST':
        form = ProprietaireSignUpForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                # 1. Création de l'utilisateur
                user = form.save(commit=False)
                user.user_type = 'PROPRIETAIRE'
                user.is_verified = False
                user.save()

                # 2. Création du profil propriétaire
                profile = ProprietaireProfile.objects.create(
                    user=user,
                    cin=form.cleaned_data['cin'],
                    address=form.cleaned_data['address'],
                    assurance_document=request.FILES.get('assurance_document'),
                    carte_grise_document=request.FILES.get('carte_grise_document')
                )

                # 3. Gestion des documents et statut
                documents_count = profile.documents_count
                if documents_count > 0:
                    user.verification_status = 'pending'
                    DocumentVerification.objects.create(
                        user=user,
                        status='en_attente'
                    )
                    log_msg = "avec documents" 
                else:
                    user.verification_status = 'documents_required'
                    log_msg = "sans documents"
                user.save()

                # 4. Connexion automatique
                user.backend = 'django.contrib.auth.backends.ModelBackend'
                login(request, user)

                # 5. Notification admin
                if getattr(settings, 'ADMIN_NOTIFICATIONS', False):
                    send_mail(
                        subject=f"Nouveau propriétaire ({log_msg}): {user.email}",
                        message=self._format_admin_notification(user, profile),
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[settings.ADMIN_EMAIL],
                        fail_silently=True
                    )

                # 6. Logging
                logger.info(
                    f"Nouveau propriétaire {log_msg} - ID:{user.id} "
                    f"Email:{user.email} Docs:{documents_count}/2 "
                    f"Assurance:{bool(profile.assurance_document)} "
                    f"CarteGrise:{bool(profile.carte_grise_document)}"
                )

                # 7. Redirection adaptée
                return self._handle_redirect(request, profile)

            except Exception as e:
                logger.error(
                    f"Erreur inscription - Email:{form.cleaned_data.get('email')} "
                    f"Erreur:{str(e)}", exc_info=True
                )
                messages.error(
                    request,
                    "Une erreur est survenue. Notre équipe a été notifiée."
                )
        else:
            logger.warning(f"Formulaire invalide - Erreurs: {form.errors}")
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = ProprietaireSignUpForm()

    return render(request, 'location/auth/register_proprietaire.html', {
        'form': form,
        'document_requirements': {
            'formats': "PDF, JPG, PNG",
            'max_size': "10MB",
            'types': ["Attestation d'assurance", "Carte grise"]
        }
    })

def _format_admin_notification(user, profile):
    """Formatage du message admin"""
    docs = []
    if profile.assurance_document:
        docs.append(f"- Assurance: {profile.assurance_document.url}")
    if profile.carte_grise_document:
        docs.append(f"- Carte grise: {profile.carte_grise_document.url}")
    
    return f"""
Nouveau propriétaire inscrit:
- Nom: {user.get_full_name()}
- Email: {user.email}
- Téléphone: {user.phone}
- Documents envoyés: {len(docs)}/2
{"\n".join(docs) if docs else "Aucun document fourni"}

Accéder au profil admin: {settings.SITE_URL}/admin/location/proprietaireprofile/{profile.id}/
"""

def _handle_redirect(request, profile):
    """Gère la redirection post-inscription"""
    if profile.documents_count >= 1:
        messages.success(
            request,
            "Inscription réussie ! Votre compte est en attente de vérification."
        )
        return redirect('proprietaire_dashboard')
    else:
        messages.warning(
            request,
            "Inscription réussie ! Complétez votre profil en uploadant vos documents."
        )
        return redirect('upload_documents')
    
@never_cache
@transaction.atomic
@require_http_methods(["GET", "POST"])
def register_loueur(request):
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')

    if request.method == 'POST':
        form = LoueurSignUpForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            
            backend = load_backend('django.contrib.auth.backends.ModelBackend')
            user.backend = f"{backend.__module__}.{backend.__class__.__name__}"
            
            login(request, user)
            messages.success(request, "Inscription réussie !")
            return redirect('loueur_dashboard')
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = LoueurSignUpForm()
    
    return render(request, 'location/auth/register_loueur.html', {'form': form})

@login_required
@require_http_methods(["GET", "POST"])
def modifier_profil(request):
    # Chemin vers l'avatar par défaut
    DEFAULT_AVATAR = '/static/location/images/default-avatar.png'
    
    if request.method == 'POST':
        form = ProfilForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            # Gestion avancée de la photo de profil
            if 'photo' in request.FILES:
                # Suppression de l'ancienne photo si elle existe
                if request.user.photo:
                    try:
                        if os.path.exists(request.user.photo.path):
                            default_storage.delete(request.user.photo.path)
                    except Exception as e:
                        logger.error(f"Erreur suppression ancienne photo : {str(e)}")
            
            # Sauvegarde du formulaire
            user = form.save(commit=False)
            
            # Validation supplémentaire pour les propriétaires
            if user.user_type == 'PROPRIETAIRE' and not user.is_verified:
                user.verification_status = 'documents_required'
            
            user.save()
            
            messages.success(request, "Votre profil a été mis à jour avec succès")
            return redirect('modifier_profil')
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous")
    else:
        form = ProfilForm(instance=request.user)
    
    # Préparation du contexte avec gestion des erreurs
    context = {
        'form': form,
        'has_photo': request.user.photo and bool(request.user.photo.url),
        'photo_url': request.user.photo.url if request.user.photo and request.user.photo.url else DEFAULT_AVATAR,
        'user': request.user,
        'verification_pending': request.user.user_type in ['LOUEUR', 'PROPRIETAIRE'] and not request.user.is_verified
    }
    
    return render(request, 'location/auth/modifier_profil.html', context)
    
@login_required
def dashboard_redirect(request):
    if request.user.user_type == 'PROPRIETAIRE':
        reservations = Reservation.objects.filter(
            voiture__proprietaire=request.user,
            statut='termine'
        )
        total = sum(r.calculer_commissions()['commission_proprietaire'] for r in reservations)
        
        messages.info(request, 
            f"Vos revenus disponibles: {total:,} XOF (après commission)")
        return redirect('proprietaire_dashboard')
    else:
        return redirect('loueur_dashboard')
        
@login_required
def parrainage(request):
    if request.user.user_type == 'PROPRIETAIRE':
        messages.warning(request, "Le parrainage n'est pas disponible pour les propriétaires")
        return redirect('dashboard_redirect')
    
    code_parrain = request.GET.get('ref')
    if code_parrain:
        try:
            parrain = User.objects.get(username=code_parrain, user_type='LOUEUR')
            request.user.parrain = parrain
            request.user.save()
            messages.success(request, f"Vous parrainez par {parrain.get_full_name()}")
        except User.DoesNotExist:
            messages.error(request, "Code parrain invalide ou non trouvé")
    
    return render(request, 'location/auth/parrainage.html')

@login_required
def mes_filleuls(request):
    if request.user.user_type == 'PROPRIETAIRE':
        messages.warning(request, "Le parrainage n'est pas disponible pour les propriétaires")
        return redirect('dashboard_redirect')
    
    filleuls = request.user.filleuls.filter(user_type='LOUEUR')
    return render(request, 'location/auth/mes_filleuls.html', {'filleuls': filleuls})

@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def upload_documents(request):
    """
    Vue pour l'upload des documents des propriétaires.
    Gère l'enregistrement des documents d'assurance et de carte grise.
    """
    if not hasattr(request.user, 'proprietaire_profile'):
        raise Http404("Cette page n'est pas disponible pour votre profil")

    profile = request.user.proprietaire_profile
    
    if request.method == 'POST':
        form = ProprietaireDocumentsForm(request.POST, request.FILES, instance=profile)
        
        if form.is_valid():
            try:
                # Sauvegarde des documents
                profile = form.save(commit=False)
                
                # Ne mettre à jour que si un nouveau fichier est fourni
                for field_name in ['assurance_document', 'carte_grise_document']:
                    if field_name in form.changed_data:
                        setattr(profile, field_name, form.cleaned_data[field_name])
                
                profile.save()
                
                # Mise à jour du statut de vérification
                has_documents = profile.assurance_document or profile.carte_grise_document
                if has_documents:
                    request.user.verification_status = 'pending'
                    request.user.save()
                    messages.success(
                        request, 
                        "Documents enregistrés avec succès ! Votre compte est en cours de vérification."
                    )
                else:
                    messages.warning(
                        request,
                        "Aucun nouveau document n'a été téléchargé. Veuillez fournir au moins un document."
                    )
                    return render(request, 'location/auth/upload_documents.html', {
                        'form': form,
                        'existing_docs': {
                            'assurance': bool(profile.assurance_document),
                            'carte_grise': bool(profile.carte_grise_document)
                        }
                    })
                
                return redirect('proprietaire_dashboard')
                
            except Exception as e:
                logger.error(f"Erreur lors de l'enregistrement des documents: {str(e)}", exc_info=True)
                messages.error(
                    request,
                    "Une erreur technique est survenue lors de l'enregistrement. Veuillez réessayer."
                )
        else:
            messages.error(
                request,
                "Erreur dans le formulaire. Veuillez vérifier les informations fournies."
            )
            logger.warning(f"Erreurs de formulaire: {form.errors}")
    else:
        form = ProprietaireDocumentsForm(instance=profile)

    context = {
        'form': form,
        'existing_docs': {
            'assurance': bool(profile.assurance_document),
            'carte_grise': bool(profile.carte_grise_document)
        },
        'document_requirements': {
            'max_size': "10MB",
            'formats': "PDF, JPG, JPEG, PNG"
        }
    }
    
    return render(request, 'location/auth/upload_documents.html', context)
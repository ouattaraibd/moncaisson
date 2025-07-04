import logging
from django.contrib import messages 
from django.shortcuts import render, redirect
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import cache_page, never_cache
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.decorators import method_decorator
from django.db.models import Prefetch, Count, Sum, Q, Max
from django.urls import reverse
from django.core.cache import cache
from datetime import datetime, date
from django.utils.safestring import mark_safe
from django.views.generic import View
from django.utils import timezone
from django.utils.html import escape
import json
from location.models.core_models import Voiture, Reservation, DocumentVerification, Favoris, ProprietaireProfile, DrivingHistory
from ..services.trust_service import TrustService
from ..permissions import proprietaire_required, loueur_required
from location.forms import LoueurPreferencesForm, DrivingLicenseForm
from .utils import calculate_occupancy_rate, verifier_disponibilite
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

logger = logging.getLogger(__name__)

def is_proprietaire(user):
    """Vérifie que l'utilisateur est un propriétaire avec gestion des cas edge"""
    return hasattr(user, 'user_type') and user.user_type == 'PROPRIETAIRE'

@never_cache
@login_required
@user_passes_test(is_proprietaire)
def proprietaire_dashboard(request):
    # Debug avancé des documents
    profile, created = ProprietaireProfile.objects.get_or_create(user=request.user)
    logger.info(
        f"Dashboard accès - User: {request.user.id}, "
        f"Assurance: {profile.assurance_document.name if profile.assurance_document else 'None'}, "
        f"Carte Grise: {profile.carte_grise_document.name if profile.carte_grise_document else 'None'}"
    )

    # Vérification de vérification utilisateur
    if not request.user.is_verified:
        logger.warning(f"User {request.user.id} non vérifié - redirection vers verification_pending")
        return render(request, 'location/auth/verification_pending.html', status=403)
    
    # Vérification des documents avec gestion améliorée
    missing_docs = []
    doc_status = {
        'assurance': bool(profile.assurance_document),
        'carte_grise': bool(profile.carte_grise_document)
    }
    
    for doc_name, exists in doc_status.items():
        if not exists:
            missing_docs.append(doc_name)
            logger.debug(f"Document manquant: {doc_name} pour user {request.user.id}")

    if missing_docs:
        warning_msg = (
            f"Documents manquants requis: {', '.join(missing_docs)}. "
            f"<a href='{reverse('upload_documents')}' class='alert-link'>Cliquez ici pour les ajouter</a>"
        )
        messages.warning(request, escape(warning_msg))
        logger.info(f"Documents manquants alertés pour user {request.user.id}: {missing_docs}")

    try:
        today = timezone.now().date()
        current_month = today.month
        current_year = today.year
        
        # Optimisation des requêtes pour les voitures
        voitures = Voiture.objects.filter(
            proprietaire=request.user
        ).select_related('proprietaire').prefetch_related(
            'photos',
            Prefetch('reservations',
                queryset=Reservation.objects.select_related('client')
                                          .filter(statut='confirme')
                                          .order_by('-date_debut'))
        ).annotate(
            nb_reservations=Count('reservations'),
            revenus_total=Sum('reservations__montant_paye'),
            derniere_reservation=Max('reservations__date_fin')
        )

        # Requêtes optimisées pour les réservations
        reservations_actives = Reservation.objects.filter(
            voiture__proprietaire=request.user,
            statut='confirme',
            date_debut__lte=today,
            date_fin__gte=today
        ).select_related('voiture', 'client')
        
        reservations_futures = Reservation.objects.filter(
            voiture__proprietaire=request.user,
            statut='confirme',
            date_debut__gt=today
        ).select_related('voiture', 'client')
        
        reservations_passees = Reservation.objects.filter(
            voiture__proprietaire=request.user,
            statut='confirme',
            date_fin__lt=today
        ).select_related('voiture', 'client')
        
        # Calcul des revenus du mois
        revenus_mois = Reservation.objects.filter(
            voiture__proprietaire=request.user,
            statut='confirme',
            date_debut__month=current_month,
            date_debut__year=current_year
        ).aggregate(total=Sum('montant_paye'))['total'] or 0
        
        # Calcul des revenus totaux
        revenus_total = sum(
            v.revenus_total for v in voitures 
            if v.revenus_total is not None
        ) or 0

        # Préparation du contexte optimisé
        context = {
            # Données véhicules
            'voitures': list(voitures) if voitures.exists() else [],
            'voitures_count': voitures.count(),
            'voitures_list': voitures[:5],  # Pour l'affichage limité
            
            # Réservations
            'reservations_actives': reservations_actives,
            'reservations_futures': reservations_futures,
            'reservations_passees': reservations_passees,
            'reservations_attente': Reservation.objects.filter(
                voiture__proprietaire=request.user,
                statut='attente'
            ).select_related('client', 'voiture')[:10],
            
            # Statistiques réservations
            'nb_reservations_actives': reservations_actives.count(),
            'nb_reservations_futures': reservations_futures.count(),
            'nb_reservations_passees': reservations_passees.count(),
            'nb_reservations_attente': Reservation.objects.filter(
                voiture__proprietaire=request.user,
                statut='attente'
            ).count(),
            
            # Finances
            'revenus': float(revenus_total),
            'revenus_mois': float(revenus_mois),
            'revenus_formatted': "{:,.0f}".format(float(revenus_mois)),  # Formaté pour l'affichage
            'taux_occupation': float(calculate_occupancy_rate(request.user)) if hasattr(request.user, 'is_verified') else 0.0,
            
            # Vérification
            'user_is_verified': bool(getattr(request.user, 'is_verified', False)),
            'verification_status': str(getattr(request.user, 'verification_status', 'non_verifie')),
            'documents_complet': bool(all(doc_status.values())) if doc_status else False,
            'missing_docs': list(missing_docs) if missing_docs else [],
            
            # Trust system
            'trust_score': int(getattr(request.user, 'trust_score', 50)),
            'trust_metrics': dict(getattr(request.user, 'trust_metrics', {})),
            
            # Paramètres GET
            'ville': request.GET.get('ville', ''),
            
            # Métadonnées
            'now': today,
            'current_month': current_month,
            'current_year': current_year,
            'has_profile': True,
            'profile': profile,
            
            # Pour les templates - CORRECTION: utilisation de user.photo au lieu de profile.photo
            'user': request.user,
            'profile_photo': request.user.photo.url if hasattr(request.user, 'photo') and request.user.photo else None
        }

        logger.info(f"Dashboard chargé avec succès pour user {request.user.id}")
        return render(request, 'location/dashboard/proprietaire.html', context)

    except Exception as e:
        logger.error(
            f"Erreur tableau de bord propriétaire - User: {request.user.id} - Erreur: {str(e)}",
            exc_info=True,
            extra={
                'user': request.user.id,
                'documents_status': doc_status
            }
        )
        messages.error(
            request,
            "Une erreur technique est survenue. Notre équipe a été notifiée."
        )
        return redirect('accueil')

@never_cache
@login_required
@user_passes_test(lambda u: u.user_type == 'LOUEUR')
def loueur_dashboard(request):
    """Vue améliorée avec plus de statistiques et d'informations"""
    try:
        # Récupération du profil loueur
        profile = request.user.loueur_profile
        
        # Optimisation des requêtes
        reservations = Reservation.objects.filter(
            client=request.user
        ).select_related(
            'voiture__proprietaire'
        ).prefetch_related(
            'voiture__photos'
        ).order_by('-date_creation')

        today = timezone.now().date()
        
        # Calcul des dépenses totales
        total_depense = Reservation.objects.filter(
            client=request.user,
            statut='confirme'
        ).aggregate(total=Sum('montant_paye'))['total'] or 0
        
        # Récupération des favoris - CORRIGÉ: utilisateur au lieu de user
        favoris = Favoris.objects.filter(utilisateur=request.user).select_related('voiture')
        
        # Nouveaux indicateurs
        total_reservations = reservations.count()
        upcoming_reservations = reservations.filter(
            date_debut__gt=today,
            statut='confirme'
        ).count()
        past_reservations = reservations.filter(
            date_fin__lt=today
        ).count()
        
        # Calcul des dépenses par catégorie
        spending_by_category = Voiture.objects.filter(
            reservations__client=request.user
        ).values('type_vehicule').annotate(
            total=Sum('reservations__montant_paye')
        )
        
        # Suggestions améliorées
        favorite_types = profile.preferred_vehicle_types or ['berline', 'suv']
        voitures_suggerees = Voiture.objects.filter(
            disponible=True,
            type_vehicule__in=favorite_types
        ).exclude(
            reservations__client=request.user
        ).prefetch_related('photos').order_by('?')[:4]

        context = {
            'profile': profile,
            'profile_photo': request.user.photo.url if request.user.photo else '/static/location/images/default-avatar.png',
            'reservations_en_cours': [r for r in reservations if r.est_en_cours],
            'reservations_futures': [r for r in reservations if r.date_debut > today and r.statut == 'confirme'],
            'reservations_passees': [r for r in reservations if r.date_fin < today],
            'total_reservations': total_reservations,
            'upcoming_reservations': upcoming_reservations,
            'past_reservations': past_reservations,
            'spending_by_category': spending_by_category,
            'license_expired': not profile.license_is_valid if profile.license_expiry else False,
            'suggestions': voitures_suggerees,
            'today': today,
            'total_depense': total_depense,
            'favoris': favoris,
            'ville': request.GET.get('ville', '')
        }
        
        return render(request, 'location/dashboard/loueur.html', context)

    except Exception as e:
        logger.error(f"Erreur dashboard loueur: {str(e)}", exc_info=True)
        messages.error(request, "Une erreur est survenue")
        return redirect('accueil')

@never_cache
@proprietaire_required
def statistiques_proprietaire(request):
    voitures = Voiture.objects.filter(
        proprietaire=request.user
    ).prefetch_related('reservations')
    
    today = datetime.now()
    revenus_mensuels = []
    
    # Calcul des revenus sur 12 mois avec cache
    cache_key = f'stats_revenus_{request.user.id}'
    revenus_mensuels = cache.get(cache_key)
    
    if not revenus_mensuels:
        revenus_mensuels = []
        for i in range(12):
            month = today.month - i - 1
            year = today.year
            if month < 1:
                month += 12
                year -= 1
            
            total = sum(
                r.montant_paye for r in Reservation.objects.filter(
                    voiture__proprietaire=request.user,
                    date_debut__month=month,
                    date_debut__year=year,
                    statut='confirme'
                )
            )
            revenus_mensuels.insert(0, total)
        
        cache.set(cache_key, revenus_mensuels, 3600)  # Cache 1 heure
    
    context = {
        'revenus_total': sum(revenus_mensuels),
        'reservations_count': sum(len(v.reservations.all()) for v in voitures),
        'voitures_count': len(voitures),
        'taux_occupation': calculate_occupancy_rate(request.user),
        'top_voitures': sorted(voitures, key=lambda v: len(v.reservations.all()), reverse=True)[:5],
        'revenus_mensuels': json.dumps(revenus_mensuels),
        'user_is_verified': request.user.is_verified
    }
    return render(request, 'location/dashboard/statistiques.html', context)

def liste_reservations(request):
    reservations = Reservation.objects.filter(
        voiture__proprietaire=request.user
    ).select_related('voiture', 'client').order_by('-date_debut')

    context = {
        'reservations': reservations,
        'user_is_verified': request.user.is_verified
    }
    return render(request, 'location/dashboard/reservations.html', context)
    
@login_required
@never_cache
def dashboard_redirect(request):
    """Redirection sécurisée vers le bon tableau de bord"""
    try:
        if not hasattr(request.user, 'user_type'):
            messages.error(request, "Type d'utilisateur non défini")
            return redirect('modifier_profil')

        # Debug logging
        logger.info(f"Redirection pour user {request.user.id} (type: {request.user.user_type})")

        if request.user.is_superuser:
            return redirect('/admin/')
        elif request.user.user_type == 'PROPRIETAIRE':
            return redirect('proprietaire_dashboard')
        elif request.user.user_type == 'LOUEUR':
            return redirect('loueur_dashboard')
        else:
            messages.error(request, "Type d'utilisateur non reconnu")
            return redirect('accueil')

    except Exception as e:
        logger.error(f"Erreur redirection dashboard: {str(e)}", exc_info=True)
        return redirect('accueil')
        
@login_required
@user_passes_test(lambda u: u.user_type == 'LOUEUR')
def loueur_driving_history(request):
    """Affiche l'historique de conduite du loueur"""
    history = DrivingHistory.objects.filter(
        loueur=request.user
    ).order_by('-start_date')
    
    return render(request, 'location/loueur/driving_history.html', {
        'history': history
    })

@login_required
@user_passes_test(lambda u: u.user_type == 'LOUEUR')
def loueur_preferences(request):
    """Gère les préférences du loueur"""
    profile = request.user.loueur_profile
    
    if request.method == 'POST':
        form = LoueurPreferencesForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Préférences mises à jour avec succès")
            return redirect('loueur_preferences')
    else:
        # Initialise les préférences si vide
        if not profile.preferred_vehicle_types:
            profile.preferred_vehicle_types = ['berline', 'suv']
            profile.save()
        form = LoueurPreferencesForm(instance=profile)
    
    return render(request, 'location/loueur/preferences.html', {
        'form': form,
        'profile': profile  # Ajout du profil au contexte
    })

@login_required
@user_passes_test(lambda u: u.user_type == 'LOUEUR')
def update_license(request):
    """Met à jour les informations du permis de conduire"""
    if request.method == 'POST':
        form = DrivingLicenseForm(request.POST, instance=request.user.loueur_profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Permis de conduire mis à jour")
            return redirect('loueur_dashboard')
    else:
        form = DrivingLicenseForm(instance=request.user.loueur_profile)
    
    return render(request, 'location/loueur/update_license.html', {
        'form': form
    })
    
def user_profile(request):
    trust_data = TrustService.calculate_user_trust_score(request.user)
    context = {
        'trust_score': trust_data['score'],
        'trust_metrics': trust_data['metrics']
    }
    return render(request, 'dashboard/profile.html', context)


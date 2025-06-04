from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required, user_passes_test
from django.http import HttpResponseForbidden, HttpResponse
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils import timezone
from django.http import Http404
from django.db import transaction
from datetime import date, timedelta
import logging
from xhtml2pdf import pisa
import tempfile

from location.models import Voiture, Reservation, Favoris, LoyaltyProfile 
from location.models.loyalty_models import LoyaltyProfile
from location.forms import ReservationForm

logger = logging.getLogger(__name__)

@login_required
@user_passes_test(lambda u: u.is_verified, login_url='/connexion/')
def reserver_voiture(request, voiture_id):
    """
    Gère le processus complet de réservation d'une voiture avec :
    - Vérification des permissions
    - Validation des dates
    - Calcul des montants (base, chauffeur, frais service)
    - Gestion de la caution
    - Création transactionnelle de la réservation
    """
    try:
        # 1. Récupération de la voiture avec son propriétaire
        voiture = Voiture.objects.select_related('proprietaire').get(id=voiture_id)
        logger.info(f"Tentative réservation - Voiture:{voiture_id}, User:{request.user.id}")

    except Voiture.DoesNotExist:
        logger.error(f"Voiture inexistante - ID:{voiture_id}")
        messages.error(request, "La voiture demandée n'existe pas")
        return redirect('voiture_list')

    # 2. Vérifications préalables
    if request.user.user_type != 'LOUEUR':
        messages.error(request, "Réservation réservée aux loueurs")
        return redirect('voiture_detail', pk=voiture_id)
    
    if not request.user.is_verified:
        messages.warning(request, "Vérification d'identité requise")
        return redirect('upload_verification')

    if not voiture.est_disponible:
        messages.error(request, "Véhicule indisponible")
        return redirect('voiture_detail', pk=voiture_id)

    # 3. Gestion du formulaire
    if request.method == 'POST':
        form = ReservationForm(request.POST, voiture=voiture)
        if form.is_valid():
            date_debut = form.cleaned_data['date_debut']
            date_fin = form.cleaned_data['date_fin']
            avec_chauffeur = form.cleaned_data.get('avec_chauffeur', False)
            today = timezone.now().date()

            # 4. Validation des dates
            if date_debut < today:
                messages.error(request, "Date début dans le passé")
                return redirect('reserver_voiture', voiture_id=voiture_id)
                
            if date_fin <= date_debut:
                messages.error(request, "Date fin invalide")
                return redirect('reserver_voiture', voiture_id=voiture_id)
            
            if (date_fin - date_debut).days > 30:
                messages.error(request, "Durée max: 30 jours")
                return redirect('reserver_voiture', voiture_id=voiture_id)
            
            if not voiture.est_disponible_pour_periode(date_debut, date_fin):
                messages.error(request, "Dates indisponibles")
                return redirect('reserver_voiture', voiture_id=voiture_id)

            # 5. Création transactionnelle
            try:
                with transaction.atomic():
                    reservation = form.save(commit=False)
                    reservation.voiture = voiture
                    reservation.client = request.user
            
                    # Calcul des montants
                    nb_jours = (date_fin - date_debut).days
                    montant_base = voiture.prix_jour * nb_jours
                    montant_chauffeur = voiture.prix_chauffeur * nb_jours if avec_chauffeur else 0
                    frais_service = round(Decimal((montant_base + montant_chauffeur) * Decimal('0.10')))
                    
                    # Gestion caution
                    caution = voiture.caution_amount if voiture.caution_required else 0
                    
                    # Assignation des valeurs
                    reservation.montant_paye = montant_base + montant_chauffeur
                    reservation.frais_service = frais_service
                    reservation.montant_total = montant_base + montant_chauffeur + frais_service + caution
                    reservation.caution_paid = caution
                    reservation.caution_status = 'pending' if caution > 0 else 'not_required'
                    reservation.statut = 'attente_paiement'
                    reservation.avec_chauffeur = avec_chauffeur
            
                    reservation.save()
                    
                    # 6. Message de confirmation adapté
                    msg = f"""
                    Réservation enregistrée! 
                    - Total: {reservation.montant_total:,} XOF
                    - Dont {frais_service:,} XOF de frais
                    """
                    if caution > 0:
                        msg += f"\n- Caution: {caution:,} XOF"
                    if avec_chauffeur:
                        msg += f"\n- Chauffeur: {montant_chauffeur:,} XOF"
                    
                    messages.success(request, msg)
                    return redirect('initier_paiement', reservation_id=reservation.id)
                    
            except Exception as e:
                logger.critical(f"Erreur création réservation: {str(e)}", exc_info=True)
                messages.error(request, "Erreur technique - Contactez le support")
                return redirect('voiture_detail', pk=voiture_id)
        else:
            messages.error(request, "Formulaire invalide")
            logger.warning(f"Erreurs formulaire: {form.errors}")
    else:
        # Valeurs par défaut
        form = ReservationForm(initial={
            'date_debut': timezone.now().date() + timedelta(days=1),
            'date_fin': timezone.now().date() + timedelta(days=2),
            'avec_chauffeur': voiture.avec_chauffeur
        })

    # 7. Préparation du contexte
    context = {
        'form': form,
        'voiture': voiture,
        'min_date': (timezone.now().date() + timedelta(days=1)).strftime('%Y-%m-%d'),
        'max_date': (timezone.now().date() + timedelta(days=365)).strftime('%Y-%m-%d'),
        'avec_chauffeur': voiture.avec_chauffeur,
        'prix_chauffeur': voiture.prix_chauffeur if voiture.avec_chauffeur else 0,
        'prix_jour': voiture.prix_jour,
        'caution_amount': voiture.caution_amount if voiture.caution_required else 0,
        'caution_required': voiture.caution_required,
        'today': timezone.now().date().strftime('%Y-%m-%d')
    }
    
    return render(request, 'location/reservation.html', context)

@login_required
def confirmer_reservation(request, reservation_id):
    """Confirme une réservation"""
    reservation = get_object_or_404(Reservation, id=reservation_id)
    reservation.statut = 'confirme'
    reservation.save()
    return redirect('mes_reservations')

@login_required
def annuler_reservation(request, reservation_id):
    reservation = get_object_or_404(
        Reservation.objects.select_related('voiture__proprietaire', 'client'),
        id=reservation_id
    )
    
    if request.user not in [reservation.client, reservation.voiture.proprietaire]:
        return HttpResponseForbidden()
    
    reservation.statut = 'annule'
    reservation.save()
    messages.success(request, "Réservation annulée")
    return redirect('dashboard')

@login_required
def generer_facture(request, pk):
    reservation = get_object_or_404(Reservation, pk=pk)
    html_string = render_to_string('location/paiement/facture.html', {'reservation': reservation})
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename=facture_{reservation.id}.pdf'
    pisa.CreatePDF(html_string, dest=response)
    
    return response

@permission_required('location.can_manage_reservations', raise_exception=True)
def gestion_reservations(request):
    return render(request, 'location/reservations/gestion.html')

@login_required
@login_required
def mes_reservations(request):
    """
    Affiche les réservations de l'utilisateur avec filtrage par statut
    """
    reservations = Reservation.objects.filter(
        client=request.user,
        statut__in=['confirme', 'attente_paiement', 'termine']
    ).select_related('voiture', 'voiture__proprietaire').order_by('-date_creation')
    
    # Ajout du dernier paiement pour chaque réservation
    for reservation in reservations:
        reservation.dernier_paiement = reservation.paiements.order_by('-date_creation').first()
    
    context = {
        'reservations': reservations,
        'now': timezone.now().date(),
        'statuts': dict(Reservation.STATUT_CHOICES)
    }
    
    return render(request, 'location/reservations/list.html', context)

@login_required
def reservations_proprietaire(request):
    """Affiche les réservations des voitures du propriétaire"""
    reservations = Reservation.objects.filter(
        voiture__proprietaire=request.user
    ).select_related('client', 'voiture').order_by('-date_creation')
    
    context = {
        'reservations': reservations,
        'now': timezone.now().date()
    }
    return render(request, 'location/reservations/proprietaire_list.html', context)
    
@login_required
def reservation_detail(request, reservation_id):
    """Détails d'une réservation"""
    reservation = get_object_or_404(
        Reservation.objects.select_related('voiture', 'client'),
        Q(client=request.user) | Q(voiture__proprietaire=request.user),  # Positionnel d'abord
        id=reservation_id  # Nommé ensuite
    )
    return render(request, 'location/reservations/detail.html', {
        'reservation': reservation
    })

def verifier_disponibilite(voiture_id, date_debut, date_fin):
    return not Reservation.objects.filter(
        voiture_id=voiture_id,
        date_debut__lte=date_fin,
        date_fin__gte=date_debut,
        statut__in=['attente_paiement', 'confirme']
    ).exists()
    
@login_required
def annuler_reservation(request, reservation_id):
    """Annule une réservation"""
    reservation = get_object_or_404(Reservation, id=reservation_id)
    reservation.statut = 'annule'
    reservation.save()
    return redirect('mes_reservations')
from django.contrib import messages
from django.shortcuts import render, redirect
from .models import Voiture, Reservation, DocumentVerification, Evaluation
from .forms import VoitureForm, ReservationForm, ProprietaireSignUpForm, LoueurSignUpForm, ProprietaireSignUpForm, LoueurSignUpForm, ProfilForm, EvaluationForm
from django.contrib.auth import login, logout
import requests
from django.core.files.storage import default_storage
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.db.models import Q, Sum, Count
from datetime import date, datetime, timedelta
from django.db import models
from .forms import VerificationForm
import json
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache, cache_page
from django.views.decorators.csrf import csrf_protect
from django.core.paginator import Paginator

def accueil(request):
    voitures = Voiture.objects.filter(disponible=True)
    return render(request, 'location/accueil.html', {'voitures': voitures})
    
def connexion(request):
    return LoginView.as_view(
        template_name='location/connexion.html',
        authentication_form=AuthenticationForm,
        redirect_authenticated_user=True
    )(request)
    
@never_cache
@csrf_protect
def deconnexion(request):
    logout(request)
    return redirect('accueil')


@login_required
def ajouter_voiture(request):
    # Vérification pour propriétaire
    if request.user.user_type != 'PROPRIETAIRE':
        messages.error(request, "Seuls les propriétaires peuvent ajouter des véhicules")
        return redirect('accueil')
        
    if not request.user.is_verified:
        messages.warning(request, "Vous devez vérifier votre identité avant d'ajouter un véhicule")
        return redirect('upload_verification')

    if request.method == 'POST':
        form = VoitureForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                voiture = form.save(commit=False)
                voiture.proprietaire = request.user
                
                # Valeurs par défaut pour les champs techniques
                voiture.transmission = form.cleaned_data.get('transmission', 'A')
                voiture.climatisation = form.cleaned_data.get('climatisation', True)
                voiture.bluetooth = form.cleaned_data.get('bluetooth', True)
                
                # Validation supplémentaire
                if voiture.prix_jour < 1000:
                    messages.error(request, "Le prix journalier minimum est de 1000 XOF")
                    return render(request, 'location/ajouter_voiture.html', {'form': form})
                
                voiture.save()
                
                messages.success(request, "Véhicule ajouté avec succès!")
                return redirect('proprietaire_dashboard')
                
            except Exception as e:
                messages.error(request, f"Erreur lors de l'ajout du véhicule: {str(e)}")
                # Log l'erreur pour le débogage
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Erreur ajout voiture: {str(e)}", exc_info=True)
        else:
            # Affichez les erreurs spécifiques
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = VoitureForm(initial={
            'transmission': 'A',
            'climatisation': True,
            'bluetooth': True
        })
    
    context = {
        'form': form,
        'user_is_verified': request.user.is_verified
    }
    return render(request, 'location/ajouter_voiture.html', context)
    
def inscription(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('accueil')
    else:
        form = UserCreationForm()
    return render(request, 'location/inscription.html', {'form': form})

def connexion(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('accueil')
    else:
        form = AuthenticationForm()
    return render(request, 'location/connexion.html', {'form': form})
    
@csrf_exempt
def initier_paiement(request):
    if request.method == 'POST':
        montant = request.POST.get('montant')
        telephone = request.POST.get('telephone')

        url = "https://api.cinetpay.com/v2/payment"
        payload = {
            "apikey": "VOTRE_CLE_API",
            "site_id": "VOTRE_SITE_ID",
            "transaction_id": str(request.user.id) + str(int(time.time())),
            "amount": montant,
            "currency": "XOF",
            "description": "Location MONCAISSON",
            "customer_name": request.user.username,
            "customer_phone": telephone
        }
        response = requests.post(url, json=payload), timeout=10)
        return redirect(response.json()['payment_url'])
        
@login_required
def reserver_voiture(request, voiture_id):
    # Vérification de l'accès
    if request.user.user_type != 'LOUEUR':
        messages.error(request, "Seuls les loueurs peuvent effectuer des réservations")
        return redirect('voiture_detail', pk=voiture_id)
    
    if not request.user.is_verified:
        messages.warning(
            request,
            "Vous devez compléter la vérification d'identité avant de pouvoir réserver un véhicule. "
            "Cette procédure ne prend que quelques minutes."
        )
        return redirect('upload_verification')

    voiture = get_object_or_404(Voiture, id=voiture_id)
    
    # Vérification de la disponibilité du véhicule
    if not voiture.disponible:
        messages.error(request, "Ce véhicule n'est actuellement pas disponible à la location")
        return redirect('voiture_detail', pk=voiture_id)

    if request.method == 'POST':
        form = ReservationForm(request.POST)
        if form.is_valid():
            date_debut = form.cleaned_data['date_debut']
            date_fin = form.cleaned_data['date_fin']
            
            # Validation des dates
            if date_debut < date.today():
                messages.error(request, "La date de début ne peut pas être dans le passé")
                return redirect('reserver_voiture', voiture_id=voiture_id)
                
            if date_fin <= date_debut:
                messages.error(request, "La date de fin doit être après la date de début")
                return redirect('reserver_voiture', voiture_id=voiture_id)
            
            # Vérification disponibilité
            if not verifier_disponibilite(voiture_id, date_debut, date_fin):
                messages.error(request, "Le véhicule n'est pas disponible pour les dates sélectionnées")
                return redirect('reserver_voiture', voiture_id=voiture_id)
                
            try:
                # Création de la réservation
                reservation = form.save(commit=False)
                reservation.client = request.user
                reservation.voiture = voiture
                reservation.montant_paye = voiture.prix_jour * (date_fin - date_debut).days
                reservation.statut = 'attente'  # Statut initial
                reservation.save()
                
                # Notification au propriétaire
                messages.success(
                    request,
                    f"Votre demande de réservation a bien été enregistrée. "
                    f"Montant total: {reservation.montant_paye} XOF"
                )
                return redirect('confirmer_reservation', pk=reservation.id)
                
            except Exception as e:
                logger.error(f"Erreur création réservation: {str(e)}")
                messages.error(request, "Une erreur est survenue lors de la réservation")
    else:
        # Initialisation du formulaire avec des dates par défaut
        form = ReservationForm(initial={
            'date_debut': date.today() + timedelta(days=1),
            'date_fin': date.today() + timedelta(days=2)
        })
    
    context = {
        'form': form,
        'voiture': voiture,
        'user_is_verified': request.user.is_verified,
        'min_date': date.today().strftime('%Y-%m-%d')
    }
    return render(request, 'location/reservation.html', context)
        
def verifier_disponibilite(voiture_id, date_debut, date_fin):
    conflits = Reservation.objects.filter(
        voiture_id=voiture_id,
        date_debut__lte=date_fin,
        date_fin__gte=date_debut
    )
    return not conflits.exists()
    
class ListeVoitures(ListView):
    model = Voiture
    template_name = 'location/liste_voitures.html'
    context_object_name = 'voitures'

    def get_queryset(self):
        return Voiture.objects.filter(disponible=True)
        
class RechercheVoitures(ListView):
    model = Voiture
    template_name = 'location/recherche.html'
    context_object_name = 'voitures'
    
    def get_queryset(self):
        queryset = super().get_queryset()
        if 'ville' in self.request.GET:
            queryset = queryset.filter(ville__icontains=self.request.GET['ville'])
        if 'prix_max' in self.request.GET:
            queryset = queryset.filter(prix_jour__lte=self.request.GET['prix_max'])
        return queryset
        
def register_choice(request):
    return render(request, 'location/auth/register_choice.html')

def register_proprietaire(request):
    if request.method == 'POST':
        form = ProprietaireSignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('proprietaire_dashboard')
    else:
        form = ProprietaireSignUpForm()
    return render(request, 'location/auth/register_proprietaire.html', {'form': form})

def register_loueur(request):
    if request.method == 'POST':
        form = LoueurSignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('loueur_dashboard')
    else:
        form = LoueurSignUpForm()
    return render(request, 'location/auth/register_loueur.html', {'form': form})
    
@login_required
def proprietaire_dashboard(request):
    # Vérification du type d'utilisateur et de la vérification d'identité
    if request.user.user_type != 'PROPRIETAIRE':
        messages.error(request, "Accès réservé aux propriétaires")
        return redirect('accueil')
    
    if not request.user.is_verified:
        messages.warning(
            request,
            "Vous devez compléter la vérification d'identité pour accéder au tableau de bord"
        )
        return redirect('upload_verification')
    
    # Récupérer les statistiques
    voitures = Voiture.objects.filter(proprietaire=request.user)
    reservations = Reservation.objects.filter(voiture__in=voitures).order_by('-date_debut')
    
    # Calcul des indicateurs clés
    revenus_totaux = reservations.filter(
        statut='confirme'
    ).aggregate(total=Sum('montant_paye'))['total'] or 0
    
    reservations_attente = reservations.filter(statut='attente')
    reservations_confirmees = reservations.filter(statut='confirme')
    
    # Calcul du taux d'occupation (exemple simplifié)
    taux_occupation = 0
    if voitures.exists():
        jours_dispos = 30 * voitures.count()  # Sur 30 jours
        jours_occupes = reservations_confirmees.aggregate(
            total_jours=Sum(F('date_fin') - F('date_debut'))
        )['total_jours'].days if reservations_confirmees.exists() else 0
        taux_occupation = round((jours_occupes / jours_dispos) * 100, 2) if jours_dispos > 0 else 0

    context = {
        'voitures': voitures,
        'reservations': reservations,
        'revenus': revenus_totaux,
        'reservations_attente': reservations_attente,
        'reservations_confirmees': reservations_confirmees,
        'taux_occupation': taux_occupation,
        'nb_voitures': voitures.count(),
        'user_is_verified': request.user.is_verified,
        'verification_status': getattr(request.user.verification, 'status', None)
    }
    
    return render(request, 'location/dashboard/proprietaire.html', context)

@login_required
def loueur_dashboard(request):
    if request.user.user_type != 'LOUEUR':
        return redirect('accueil')
    
    # Récupérer les réservations du loueur
    reservations = Reservation.objects.filter(client=request.user).order_by('-date_debut')
    
    # Récupérer les favoris (à implémenter dans le modèle)
    favoris = Voiture.objects.filter(favoris=request.user)
    
    context = {
        'reservations': reservations,
        'favoris': favoris,
        'reservations_en_cours': reservations.filter(date_fin__gte=date.today(), date_debut__lte=date.today()),
        'reservations_passees': reservations.filter(date_fin__lt=date.today()),
        'reservations_futures': reservations.filter(date_debut__gt=date.today()),
    }

@login_required
def confirmer_reservation(request, pk):
    reservation = get_object_or_404(Reservation, pk=pk)
    if reservation.voiture.proprietaire != request.user:
        return HttpResponseForbidden()
    
    reservation.statut = 'confirme'
    reservation.save()
    messages.success(request, "Réservation confirmée avec succès!")
    return redirect('proprietaire_dashboard')

@login_required
def annuler_reservation(request, pk):
    reservation = get_object_or_404(Reservation, pk=pk)
    if reservation.client != request.user:
        return HttpResponseForbidden()
    
    reservation.statut = 'annule'
    reservation.save()
    messages.success(request, "Réservation annulée avec succès!")
    return redirect('loueur_dashboard')

@login_required
def ajouter_favoris(request, pk):
    voiture = get_object_or_404(Voiture, pk=pk)
    voiture.favoris.add(request.user)
    messages.success(request, "Véhicule ajouté aux favoris!")
    return redirect('voiture_detail', pk=pk)

@login_required
def retirer_favoris(request, pk):
    voiture = get_object_or_404(Voiture, pk=pk)
    voiture.favoris.remove(request.user)
    messages.success(request, "Véhicule retiré des favoris!")
    return redirect('loueur_dashboard')

@login_required
def generer_facture(request, pk):
    reservation = get_object_or_404(Reservation, pk=pk, client=request.user)
    # Ici vous devrez implémenter la génération de PDF
    # Pour l'instant, retournez une réponse simple
    return HttpResponse(f"Facture pour la réservation {reservation.id}")

@login_required
def modifier_profil(request):
    if request.method == 'POST':
        form = ProfilForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Votre profil a été mis à jour avec succès!")
            return redirect('proprietaire_dashboard')
    else:
        form = ProfilForm(instance=request.user)
    
    return render(request, 'location/auth/modifier_profil.html', {'form': form})

@login_required
def statistiques_proprietaire(request):
    if request.user.user_type != 'PROPRIETAIRE':
        return redirect('accueil')

    voitures = Voiture.objects.filter(proprietaire=request.user)
    reservations = Reservation.objects.filter(voiture__in=voitures)

    # Calcul des revenus mensuels (12 derniers mois)
    revenus_mensuels = []
    today = datetime.now()
    
    for i in range(12):
        month = today.month - i - 1
        year = today.year
        if month < 1:
            month += 12
            year -= 1
        
        total = int(reservations.filter(
            date_debut__month=month,
            date_debut__year=year,
            statut='confirme'
        ).aggregate(Sum('montant_paye'))['montant_paye__sum'] or 0)
        
        revenus_mensuels.insert(0, total)

    context = {
        'revenus_total': sum(revenus_mensuels),
        'reservations_count': reservations.count(),
        'voitures_count': voitures.count(),
        'taux_occupation': calculate_occupancy_rate(request.user),
        'top_voitures': voitures.annotate(res_count=Count('reservation')).order_by('-res_count')[:5],
        'revenus_mensuels': json.dumps(revenus_mensuels),
        'reservations': reservations.order_by('-date_debut')
    }
    
    return render(request, 'location/dashboard/statistiques.html', context)
    
def calculate_occupancy_rate(user):
    from datetime import date, timedelta
    from django.db.models import F, Sum
    
    total_days = 90  # Période de 3 mois
    occupied_days = Reservation.objects.filter(
        voiture__proprietaire=user,
        statut='confirme',
        date_debut__gte=date.today() - timedelta(days=total_days)
    ).aggregate(
        total=Sum(F('date_fin') - F('date_debut'))
    )['total'] or timedelta(days=0)
    
    total_possible_days = total_days * user.voitures.count()
    return round((occupied_days.days / total_possible_days) * 100, 2) if total_possible_days > 0 else 0
    
@login_required
def liste_reservations(request):
    if request.user.user_type != 'PROPRIETAIRE':
        return redirect('accueil')
    
    voitures = Voiture.objects.filter(proprietaire=request.user)
    reservations = Reservation.objects.filter(voiture__in=voitures).order_by('-date_debut')
    
    context = {
        'reservations': reservations,
        'reservations_en_attente': reservations.filter(statut='attente'),
        'reservations_confirmees': reservations.filter(statut='confirme'),
        'reservations_annulees': reservations.filter(statut='annule')
    }
    
    return render(request, 'location/dashboard/reservations.html', context)
    
class ModifierVoiture(UpdateView):
    model = Voiture
    form_class = VoitureForm
    template_name = 'location/modifier_voiture.html'
    success_url = reverse_lazy('proprietaire_dashboard')

    def get_queryset(self):
        # Seul le propriétaire peut modifier sa voiture
        return Voiture.objects.filter(proprietaire=self.request.user)
        
class VoitureDetail(DetailView):
    model = Voiture
    template_name = 'location/voiture_detail.html'
    context_object_name = 'voiture'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['disponible'] = self.object.disponible
        return context
        
@login_required
def upload_verification(request):
    try:
        verification = request.user.verification
    except DocumentVerification.DoesNotExist:
        verification = None

    if request.method == 'POST':
        form = VerificationForm(request.POST, request.FILES, instance=verification)
        if form.is_valid():
            verification = form.save(commit=False)
            verification.user = request.user
            verification.save()
            messages.success(request, "Documents envoyés pour vérification !")
            return redirect('proprietaire_dashboard')
    else:
        form = VerificationForm(instance=verification)

    return render(request, 'location/auth/verification.html', {'form': form})

def check_verification(user):
    """Utilitaire à appeler avant les actions critiques"""
    if user.user_type == 'PROPRIETAIRE':
        if not hasattr(user, 'verification') or user.verification.status != 'approuve':
            raise PermissionDenied("Vérification d'identité requise")
            
@login_required
def ajouter_evaluation(request, voiture_id):
    voiture = get_object_or_404(Voiture, id=voiture_id)
    
    # Vérifier si l'utilisateur a déjà évalué cette voiture
    existing_eval = Evaluation.objects.filter(voiture=voiture, client=request.user).first()
    
    if request.method == 'POST':
        form = EvaluationForm(request.POST, instance=existing_eval)
        if form.is_valid():
            evaluation = form.save(commit=False)
            evaluation.voiture = voiture
            evaluation.client = request.user
            evaluation.save()
            messages.success(request, "Merci pour votre évaluation!")
            return redirect('voiture_detail', pk=voiture_id)
    else:
        form = EvaluationForm(instance=existing_eval)
    
    return render(request, 'location/partials/evaluation_form.html', {
        'form': form,
        'voiture': voiture,
        'existing_eval': existing_eval
    })
    
@cache_page(60 * 15)  # Cache pendant 15 minutes
def liste_voitures(request):
    voitures = cache.get('voitures_list')
    if not voitures:
        voitures = Voiture.objects.filter(disponible=True).select_related('proprietaire')
        cache.set('voitures_list', voitures, 60 * 15)
    return render(request, 'location/liste_voitures.html', {'voitures': voitures})
    
class RechercheVoitures(ListView):
    model = Voiture
    template_name = 'location/recherche.html'
    context_object_name = 'voitures'
    paginate_by = 10  # 10 résultats par page

    def get_queryset(self):
        queryset = super().get_queryset().filter(disponible=True)
        
        # Filtres
        ville = self.request.GET.get('ville')
        prix_max = self.request.GET.get('prix_max')
        type_vehicule = self.request.GET.get('type_vehicule')
        
        if ville:
            queryset = queryset.filter(ville__icontains=ville)
        if prix_max:
            queryset = queryset.filter(prix_jour__lte=prix_max)
        if type_vehicule:
            queryset = queryset.filter(type_vehicule=type_vehicule)
            
        return queryset.order_by('-date_creation')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['ville'] = self.request.GET.get('ville', '')
        context['prix_max'] = self.request.GET.get('prix_max', '')
        context['type_vehicule'] = self.request.GET.get('type_vehicule', '')
        return context


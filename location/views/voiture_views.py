from django.utils import timezone
from datetime import timedelta, datetime
from django.views.generic import ListView, DetailView, UpdateView, CreateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.files.storage import default_storage
from django.core.exceptions import SuspiciousFileOperation
from django.db.models import Avg, Q
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, redirect
from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import reverse
from location.models.core_models import Voiture, Favoris
from location.forms import VoitureForm, AdvancedSearchForm
from django.contrib.auth.decorators import login_required


class VoitureCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Voiture
    fields = ['marque', 'modele', 'prix_jour']  # À remplacer par un Form
    template_name = 'location/ajouter_voiture.html'
    success_url = reverse_lazy('proprietaire_dashboard')
    
    def test_func(self):
        return self.request.user.user_type == User.UserType.OWNER
    
    def form_valid(self, form):
        form.instance.proprietaire = self.request.user
        return super().form_valid(form)
        
class ListeVoitures(ListView):
    model = Voiture
    template_name = 'location/voitures/list.html'
    context_object_name = 'voitures'
    paginate_by = 10
    ordering = ['-date_creation']
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['dashboard_url'] = reverse('location:loueur_dashboard')
        return context

    def get_queryset(self):
        return Voiture.objects.filter(disponible=True)

class VoitureDetail(DetailView):
    """
    Vue détaillée d'une voiture avec :
    - Gestion améliorée de la disponibilité
    - Vérification des favoris
    - Contrôle d'accès selon le type d'utilisateur
    - Calcul des périodes de disponibilité
    """
    model = Voiture
    template_name = 'location/voiture_detail.html'
    context_object_name = 'voiture'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        voiture = self.object
        user = self.request.user
        
        # Disponibilité (utilise les nouvelles méthodes du modèle)
        context['disponible'] = voiture.est_disponible
        context['disponibilite_message'] = self.get_disponibilite_message(voiture)
        
        # Informations utilisateur
        context['user_connected'] = user.is_authenticated
        context['is_loueur'] = user.is_authenticated and user.user_type == 'LOUEUR'
        context['is_proprietaire'] = user.is_authenticated and user == voiture.proprietaire
        context['user_is_verified'] = user.is_verified if user.is_authenticated else False
        
        # Favoris
        if user.is_authenticated:
            context['in_favoris'] = Favoris.objects.filter(
                utilisateur=user,
                voiture=voiture
            ).exists()
        
        # Dates par défaut pour la réservation (demain -> après-demain)
        today = timezone.now().date()
        context['default_start_date'] = (today + timedelta(days=1)).strftime('%Y-%m-%d')
        context['default_end_date'] = (today + timedelta(days=2)).strftime('%Y-%m-%d')
        
        # Évaluations
        context['evaluations'] = voiture.evaluations.all().order_by('-date_creation')[:5]
        context['note_moyenne'] = voiture.evaluations.aggregate(Avg('note'))['note__avg']
        
        # Photos supplémentaires
        context['photos'] = voiture.photos.all()
        
        return context

    def get_disponibilite_message(self, voiture):
        """Retourne un message détaillé sur la disponibilité"""
        if not voiture.disponible:
            return "Ce véhicule est actuellement indisponible"
            
        if not voiture.est_disponible:
            next_available = self.get_next_available_date(voiture)
            return f"Disponible à partir du {next_available.strftime('%d/%m/%Y')}" if next_available else "Actuellement en location"
            
        return "Disponible immédiatement"

    def get_next_available_date(self, voiture):
        """Trouve la prochaine date de disponibilité si la voiture est actuellement occupée"""
        today = timezone.now().date()
        next_reservation = voiture.reservations.filter(
            date_fin__gte=today,
            statut='confirme'
        ).order_by('date_fin').first()
        
        return next_reservation.date_fin + timedelta(days=1) if next_reservation else None

@login_required
def ajouter_voiture(request):
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
                voiture.disponible = True  # Nouveau: Force la disponibilité à True
                voiture.transmission = form.cleaned_data.get('transmission', 'A')
                voiture.climatisation = form.cleaned_data.get('climatisation', True)
                voiture.bluetooth = form.cleaned_data.get('bluetooth', True)
                
                if voiture.prix_jour < 1000:
                    messages.error(request, "Le prix journalier minimum est de 1000 XOF")
                    return render(request, 'location/ajouter_voiture.html', {'form': form})
                
                voiture.save()
                messages.success(request, "Véhicule ajouté avec succès!")
                return redirect('proprietaire_dashboard')
                
            except Exception as e:
                messages.error(request, f"Erreur lors de l'ajout du véhicule: {str(e)}")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = VoitureForm(initial={
            'transmission': 'A',
            'climatisation': True,
            'bluetooth': True,
            'disponible': True  # Nouveau: Valeur par défaut dans le formulaire
        })
    
    return render(request, 'location/ajouter_voiture.html', {
        'form': form,
        'user_is_verified': request.user.is_verified
    })

class ModifierVoiture(UpdateView):
    model = Voiture
    form_class = VoitureForm
    template_name = 'location/modifier_voiture.html'
    success_url = '/dashboard/proprietaire/'  # À adapter

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Vérifie si le fichier existe
        context['file_exists'] = (default_storage.exists(self.object.photo.name) 
                                if self.object.photo else False)
        return context

    def form_valid(self, form):
        try:
            # Vérification de l'image existante
            if 'photo' not in self.request.FILES and form.instance.photo:
                if not default_storage.exists(form.instance.photo.name):
                    form.instance.photo = None  # Efface la référence si fichier manquant
            
            return super().form_valid(form)
            
        except SuspiciousFileOperation:
            form.add_error('photo', "Erreur de chemin de fichier")
            return self.form_invalid(form)
        
class RechercheVoitures(ListView):
    model = Voiture
    template_name = 'location/recherche.html'
    context_object_name = 'voitures'
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset().filter(disponible=True)
        form = AdvancedSearchForm(self.request.GET or None)
        
        # Filtre par ville
        ville = self.request.GET.get('ville')
        if ville:
            queryset = queryset.filter(ville__icontains=ville)

        # Filtres avancés
        if form.is_valid():
            if form.cleaned_data.get('prix_min'):
                queryset = queryset.filter(prix_jour__gte=form.cleaned_data['prix_min'])
            if form.cleaned_data.get('prix_max'):
                queryset = queryset.filter(prix_jour__lte=form.cleaned_data['prix_max'])
            if form.cleaned_data.get('transmission'):
                queryset = queryset.filter(transmission=form.cleaned_data['transmission'])
            if form.cleaned_data.get('climatisation'):
                queryset = queryset.filter(climatisation=True)
            if form.cleaned_data.get('type_vehicule'):
                queryset = queryset.filter(type_vehicule=form.cleaned_data['type_vehicule'])
        
        # Filtre par dates
        date_debut = self.request.GET.get('date_debut')
        date_fin = self.request.GET.get('date_fin')
        
        if date_debut and date_fin:
            try:
                date_debut = datetime.strptime(date_debut, '%Y-%m-%d').date()
                date_fin = datetime.strptime(date_fin, '%Y-%m-%d').date()
                
                # Exclusion des voitures avec réservations en conflit
                queryset = queryset.exclude(
                    reservations__date_debut__lt=date_fin,
                    reservations__date_fin__gt=date_debut,
                    reservations__statut='confirme'
                )
            except ValueError:
                pass
        
        # Filtre par texte
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(marque__icontains=query) | 
                Q(modele__icontains=query) |
                Q(description__icontains=query)
            )
        
        return queryset.order_by('prix_jour')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Formulaire de recherche avancée
        context['search_form'] = AdvancedSearchForm(self.request.GET or None)
        
        # Paramètres de recherche
        context.update({
            'ville': self.request.GET.get('ville', ''),
            'date_debut': self.request.GET.get('date_debut', ''),
            'date_fin': self.request.GET.get('date_fin', ''),
            'query': self.request.GET.get('q', ''),
            'prix_min': self.request.GET.get('prix_min', ''),
            'prix_max': self.request.GET.get('prix_max', ''),
            'transmission': self.request.GET.get('transmission', ''),
            'climatisation': self.request.GET.get('climatisation', ''),
            'type_vehicule': self.request.GET.get('type_vehicule', '')
        })
        
        return context
        
@login_required
def ajouter_favoris(request, pk):
    voiture = get_object_or_404(Voiture, pk=pk)
    favoris, created = Favoris.objects.get_or_create(
        utilisateur=request.user,
        voiture=voiture
    )
    if created:
        messages.success(request, f"{voiture.marque} {voiture.modele} ajouté aux favoris")
    else:
        messages.info(request, f"{voiture.marque} {voiture.modele} est déjà dans vos favoris")
    return redirect('voiture_detail', pk=pk)

@login_required
def retirer_favoris(request, pk):
    voiture = get_object_or_404(Voiture, pk=pk)
    Favoris.objects.filter(
        utilisateur=request.user,
        voiture=voiture
    ).delete()
    messages.success(request, f"{voiture.marque} {voiture.modele} retiré des favoris")
    return redirect('voiture_detail', pk=pk)
    
@login_required
def liste_favoris(request):
    favoris = Favoris.objects.filter(utilisateur=request.user).select_related('voiture')
    return render(request, 'location/favoris/list.html', {'favoris': favoris})


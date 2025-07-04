from django import forms
from decimal import Decimal
from django.contrib.auth.password_validation import validate_password
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Submit
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.core.validators import validate_email, MinValueValidator, RegexValidator, FileExtensionValidator
from django.utils import timezone
from .models import Transaction, ProprietaireProfile
from django import forms
import os
import re

from location.models.core_models import (
    User,
    Voiture,
    Reservation,
    Evaluation,
    PHONE_VALIDATOR,
    EvaluationLoueur,  # Import ajouté ici
    Transaction,
    Portefeuille,
    DocumentVerification,
    ProprietaireProfile,
    LoueurProfile
)
from location.models import ProprietaireProfile, LoueurProfile, Paiement


class CustomPasswordValidator:
    def validate(self, password, user=None):
        if len(password) < 10:
            raise ValidationError("Le mot de passe doit contenir au moins 10 caractères.")
        if not re.search(r'\d', password):
            raise ValidationError("Le mot de passe doit contenir au moins 1 chiffre.")
        if not re.search(r'[A-Z]', password):
            raise ValidationError("Le mot de passe doit contenir au moins 1 majuscule.")
        if not re.search(r'[()[\]{}|\\`~!@#$%^&*_\-+=;:\'",<>./?]', password):
            raise ValidationError("Le mot de passe doit contenir au moins 1 caractère spécial.")

    def get_help_text(self):
        return (
            "Votre mot de passe doit contenir :\n"
            "- Minimum 10 caractères\n"
            "- Au moins 1 majuscule\n"
            "- Au moins 1 chiffre\n"
            "- Au moins 1 caractère spécial"
        )

class UserRegisterForm(UserCreationForm):
    phone = forms.CharField(
        validators=[PHONE_VALIDATOR],  # Correction ici
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    city = forms.CharField(label="Ville")
    country = forms.CharField(label="Pays")

    class Meta:
        model = User
        fields = ['username', 'email', 'phone', 'city', 'country', 'password1', 'password2']

class ProprietaireSignUpForm(forms.ModelForm):
    # Nouveaux champs ajoutés
    first_name = forms.CharField(
        max_length=30,
        required=True,
        label="Prénom",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    last_name = forms.CharField(
        max_length=30,
        required=True,
        label="Nom",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    date_naissance = forms.DateField(
        required=True,
        label="Date de naissance",
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )
    phone = forms.CharField(
        validators=[PHONE_VALIDATOR],  # Correction ici
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    # Champs existants
    password1 = forms.CharField(
        label="Mot de passe",
        widget=forms.PasswordInput(attrs={
            'autocomplete': 'new-password',
            'class': 'form-control',
            'placeholder': 'Créez un mot de passe sécurisé'
        }),
        validators=[validate_password, CustomPasswordValidator().validate],
        help_text=CustomPasswordValidator().get_help_text()
    )
    password2 = forms.CharField(
        label="Confirmation du mot de passe",
        widget=forms.PasswordInput(attrs={
            'autocomplete': 'new-password',
            'class': 'form-control',
            'placeholder': 'Répétez votre mot de passe'
        })
    )
    cin = forms.CharField(
        max_length=50,
        validators=[RegexValidator(r'^[0-9]{2}[A-Za-z]{1}[0-9]{5}$')],
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    address = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        label="Adresse complète"
    )
    
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'date_naissance', 'phone', 'city', 'country', 'photo']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'country': forms.TextInput(attrs={'class': 'form-control'}),
            'photo': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
        }

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise ValidationError("Les mots de passe ne correspondent pas")
        return password2

    def clean(self):
        cleaned_data = super().clean()
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        user.user_type = 'PROPRIETAIRE'
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.date_naissance = self.cleaned_data['date_naissance']
        
        if commit:
            user.save()
            ProprietaireProfile.objects.create(
                user=user,
                cin=self.cleaned_data['cin'],
                address=self.cleaned_data['address']
            )
        return user

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ajout des classes Bootstrap et placeholders
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'
            if field.required and field.label:
                field.label = f"{field.label} *"


class LoueurSignUpForm(forms.ModelForm):
    # Nouveaux champs ajoutés
    first_name = forms.CharField(
        max_length=30,
        required=True,
        label="Prénom",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    last_name = forms.CharField(
        max_length=30,
        required=True,
        label="Nom",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    date_naissance = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    phone = forms.CharField(
        validators=[PHONE_VALIDATOR],  # Correction ici
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    # Champs existants
    password1 = forms.CharField(
        label="Mot de passe",
        widget=forms.PasswordInput(attrs={
            'autocomplete': 'new-password',
            'class': 'form-control',
            'placeholder': 'Créez un mot de passe sécurisé'
        }),
        validators=[validate_password, CustomPasswordValidator().validate],
        help_text=CustomPasswordValidator().get_help_text()
    )
    password2 = forms.CharField(
        label="Confirmation du mot de passe",
        widget=forms.PasswordInput(attrs={
            'autocomplete': 'new-password',
            'class': 'form-control',
            'placeholder': 'Répétez votre mot de passe'
        })
    )
    passport_number = forms.CharField(
        max_length=50,
        label="Numéro de passeport",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    driving_license = forms.CharField(
        max_length=50,
        label="Permis de conduire",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'date_naissance', 'phone', 'city', 'country', 'photo']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'country': forms.TextInput(attrs={'class': 'form-control'}),
            'date_naissance': forms.TextInput(attrs={'class': 'form-control'}),
            'photo': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
        }

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise ValidationError("Les mots de passe ne correspondent pas")
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        user.user_type = 'LOUEUR'
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.date_naissance = self.cleaned_data['date_naissance']
        
        if commit:
            user.save()
            LoueurProfile.objects.create(
                user=user,
                passport_number=self.cleaned_data['passport_number'],
                driving_license=self.cleaned_data['driving_license']
            )
        return user

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Uniformisation des styles
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'
            if field.required and field.label:
                field.label = f"{field.label} *"

class ProfilForm(UserChangeForm):
    photo = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*'
        }),
        help_text="Formats acceptés : JPG, JPEG, PNG, WEBP (max 5MB)"
    )
    
    class Meta:
        model = User
        fields = [
            'photo',
            'first_name', 
            'last_name',
            'email',
            'phone',
            'date_naissance',
            'city',
            'country'
        ]
        widgets = {
            'date_naissance': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Prénom'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Email'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Téléphone'
            }),
            'city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ville'
            }),
            'country': forms.Select(attrs={
                'class': 'form-control'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Masquer le champ mot de passe
        self.fields['password'].widget = forms.HiddenInput()
        self.fields['password'].required = False
        
        # Ajout des classes Bootstrap pour uniformité
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'
    
    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if photo:
            # Vérification de l'extension
            ext = os.path.splitext(photo.name)[1].lower()
            if ext not in ['.jpg', '.jpeg', '.png', '.webp']:
                raise ValidationError(
                    "Format d'image non supporté. Utilisez JPG, JPEG, PNG ou WEBP."
                )
            
            # Vérification de la taille
            if photo.size > 5 * 1024 * 1024:  # 5MB
                raise ValidationError(
                    "La taille de l'image ne doit pas dépasser 5MB"
                )
                
            # Validation supplémentaire via FileExtensionValidator
            validator = FileExtensionValidator(
                allowed_extensions=['jpg', 'jpeg', 'png', 'webp']
            )
            validator(photo)
            
        return photo

class VoitureForm(forms.ModelForm):
    class Meta:
        model = Voiture
        fields = [
            'marque', 'modele', 'annee', 'type_vehicule', 'transmission',
            'carburant', 'kilometrage', 'nb_places', 'nb_portes', 'climatisation',
            'gps', 'siege_bebe', 'bluetooth', 'prix_jour', 'ville', 'photo',
            'description', 'disponible', 'caution_amount', 'caution_required'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'photo': forms.FileInput(attrs={
                'accept': 'image/*',
                'class': 'form-control'
            }),
            'transmission': forms.Select(attrs={'class': 'form-select'}),
            'caution_amount': forms.NumberInput(attrs={
                'min': 0,
                'step': 1000,
                'class': 'form-control',
                'placeholder': 'Montant en XOF'
            }),
            'caution_required': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'onchange': "toggleCautionField(this)"
            }),
            'prix_jour': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Prix journalier en XOF'
            }),
            'ville': forms.TextInput(attrs={'class': 'form-control'}),
            'marque': forms.TextInput(attrs={'class': 'form-control'}),
            'modele': forms.TextInput(attrs={'class': 'form-control'}),
            'annee': forms.NumberInput(attrs={'class': 'form-control'}),
            'type_vehicule': forms.Select(attrs={'class': 'form-select'}),
            'carburant': forms.Select(attrs={'class': 'form-select'}),
            'kilometrage': forms.NumberInput(attrs={'class': 'form-control'}),
            'nb_places': forms.NumberInput(attrs={'class': 'form-control'}),
            'nb_portes': forms.NumberInput(attrs={'class': 'form-control'}),
            'climatisation': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'gps': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'siege_bebe': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'bluetooth': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'disponible': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'transmission': 'Transmission',
            'caution_amount': 'Montant de la caution (XOF)',
            'caution_required': 'Caution requise',
            'prix_jour': 'Prix journalier (XOF)',
            'type_vehicule': 'Type de véhicule',
            'nb_places': 'Nombre de places',
            'nb_portes': 'Nombre de portes',
            'climatisation': 'Climatisation',
            'gps': 'Système GPS',
            'siege_bebe': 'Siège bébé disponible',
            'bluetooth': 'Bluetooth',
            'disponible': 'Disponible immédiatement'
        }
        help_texts = {
            'transmission': 'Sélectionnez le type de transmission',
            'caution_amount': 'Montant qui sera bloqué pendant la location',
            'photo': 'Image principale du véhicule (max 5MB)',
            'description': 'Description détaillée du véhicule et de ses équipements'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Initialisation des valeurs pour la caution
        if self.instance and self.instance.caution_amount > 0:
            self.initial['caution_required'] = True
        else:
            self.initial['caution_amount'] = 0

    def clean_prix_jour(self):
        prix = self.cleaned_data.get('prix_jour')
        if prix is not None and prix < 1000:
            raise ValidationError("Le prix minimum est de 1000 XOF")
        if prix is not None and prix > 1000000:  # 1 000 000 XOF
            raise ValidationError("Le prix maximum est de 1 000 000 XOF")
        return prix

    def clean_caution_amount(self):
        caution = self.cleaned_data.get('caution_amount', 0)
        if caution is not None and caution > 1000000:  # 1 000 000 XOF max
            raise ValidationError("La caution ne peut excéder 1 000 000 XOF")
        return caution

    def clean_annee(self):
        annee = self.cleaned_data.get('annee')
        current_year = timezone.now().year
        if annee is not None and (annee < 1990 or annee > current_year + 1):
            raise ValidationError(f"L'année doit être entre 1990 et {current_year + 1}")
        return annee

    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if photo:
            # Vérification de l'extension
            ext = os.path.splitext(photo.name)[1].lower()
            valid_extensions = ['.jpg', '.jpeg', '.png', '.webp']
            if ext not in valid_extensions:
                raise ValidationError(
                    f"Format d'image non supporté. Formats acceptés: {', '.join(valid_extensions)}"
                )
            
            # Vérification de la taille
            max_size = 5 * 1024 * 1024  # 5MB
            if photo.size > max_size:
                raise ValidationError(
                    f"La taille de l'image ne doit pas dépasser {max_size // (1024 * 1024)}MB"
                )
        return photo

    def clean(self):
        cleaned_data = super().clean()
        caution_required = cleaned_data.get('caution_required', False)
        caution_amount = cleaned_data.get('caution_amount', 0)
        
        # Validation de la cohérence caution
        if caution_required and (caution_amount is None or caution_amount <= 0):
            self.add_error('caution_amount', "Veuillez spécifier un montant de caution valide")
        
        # Validation du kilométrage
        kilometrage = cleaned_data.get('kilometrage')
        if kilometrage is not None and kilometrage < 0:
            self.add_error('kilometrage', "Le kilométrage ne peut pas être négatif")
        
        return cleaned_data

class ReservationForm(forms.ModelForm):
    class Meta:
        model = Reservation
        fields = ['date_debut', 'date_fin']
        widgets = {
            'date_debut': forms.DateInput(attrs={'type': 'date'}),
            'date_fin': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        self.voiture = kwargs.pop('voiture', None)
        super().__init__(*args, **kwargs)
        
        today = timezone.now().date()
        self.fields['date_debut'].widget.attrs.update({
            'min': (today + timezone.timedelta(days=1)).isoformat(),
            'max': (today + timezone.timedelta(days=365)).isoformat()
        })
        self.fields['date_fin'].widget.attrs.update({
            'min': (today + timezone.timedelta(days=2)).isoformat(),
            'max': (today + timezone.timedelta(days=365)).isoformat()
        })

    def clean(self):
        cleaned_data = super().clean()
        date_debut = cleaned_data.get('date_debut')
        date_fin = cleaned_data.get('date_fin')
        
        if date_debut and date_fin:
            today = timezone.now().date()
            
            if date_debut < today:
                raise ValidationError("La date de début ne peut pas être dans le passé")
                
            if date_fin <= date_debut:
                raise ValidationError("La date de fin doit être postérieure à la date de début")
            
            if (date_fin - date_debut).days > 30:
                raise ValidationError("La durée maximale est de 30 jours")
            
            # Utilisez la méthode du modèle pour vérifier la disponibilité
            if self.voiture and not self.voiture.est_disponible_pour_periode(date_debut, date_fin):
                raise ValidationError("Le véhicule n'est pas disponible pour ces dates")
        
        return cleaned_data

class VerificationForm(forms.ModelForm):
    class Meta:
        model = DocumentVerification
        fields = []
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Champs communs
        self.fields['id_card'] = forms.FileField(
            label="Pièce d'identité (CNI/Passeport)",
            required=True,
            widget=forms.FileInput(attrs={'accept': '.pdf,.jpg,.jpeg,.png'})
        )
        
        if self.user.user_type == 'PROPRIETAIRE':
            self.fields['vehicle_insurance'] = forms.FileField(
                label="Attestation d'assurance",
                required=False,
                widget=forms.FileInput(attrs={'accept': '.pdf,.jpg,.jpeg,.png'})
            )
            self.fields['registration_card'] = forms.FileField(
                label="Carte grise",
                required=False,
                widget=forms.FileInput(attrs={'accept': '.pdf,.jpg,.jpeg,.png'})
            )
        elif self.user.user_type == 'LOUEUR':
            self.fields['driver_license'] = forms.FileField(
                label="Permis de conduire",
                required=True,
                widget=forms.FileInput(attrs={'accept': '.pdf,.jpg,.jpeg,.png'})
            )
            self.fields['passport'] = forms.FileField(
                label="Passeport (si disponible)",
                required=False,
                widget=forms.FileInput(attrs={'accept': '.pdf,.jpg,.jpeg,.png'})
            )
            self.fields['selfie'] = forms.ImageField(
                label="Photo d'identité récente",
                required=True,
                widget=forms.FileInput(attrs={'accept': 'image/*'})
            )

    def clean(self):
        cleaned_data = super().clean()
        if self.user.user_type == 'PROPRIETAIRE':
            if not cleaned_data.get('vehicle_insurance') and not cleaned_data.get('registration_card'):
                raise ValidationError("Vous devez fournir au moins un document véhicule (assurance ou carte grise)")
        return cleaned_data

class EvaluationForm(forms.ModelForm):
    class Meta:
        model = Evaluation
        fields = ['note', 'commentaire']
        widgets = {
            'commentaire': forms.Textarea(attrs={'rows': 3}),
        }
  
class AdvancedSearchForm(forms.Form):
    TRANSMISSION_CHOICES = [
        ('', 'Tous'),
        ('A', 'Automatique'),
        ('M', 'Manuelle')
    ]
    
    prix_min = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={'placeholder': 'Prix min'})
    )
    prix_max = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={'placeholder': 'Prix max'})
    )
    transmission = forms.ChoiceField(
        choices=TRANSMISSION_CHOICES,
        required=False
    )
    climatisation = forms.BooleanField(
        required=False,
        label='Avec climatisation'
    )

class DemandeRetraitForm(forms.Form):
    montant = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('10.00'))],  # Minimum 10€
        label="Montant à retirer"
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user')
        super().__init__(*args, **kwargs)
    
    def clean_montant(self):
        montant = self.cleaned_data['montant']
        if montant > self.user.portefeuille.solde:
            raise forms.ValidationError("Solde insuffisant")
        return montant   

class ValidationTransactionForm(forms.ModelForm):
    action = forms.ChoiceField(choices=[('valider', 'Valider'), ('rejeter', 'Rejeter')])
    motif_rejet = forms.CharField(required=False, widget=forms.Textarea)

    class Meta:
        model = Transaction
        fields = []        

class EvaluationLoueurForm(forms.ModelForm):
    class Meta:
        model = EvaluationLoueur
        fields = ['note', 'commentaire']
        widgets = {
            'note': forms.RadioSelect(choices=[(1, '1'), (2, '2'), (3, '3'), (4, '4'), (5, '5')]),
            'commentaire': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }
        labels = {
            'note': 'Note (1-5 étoiles)',
            'commentaire': 'Commentaire'
        }

class DocumentsForm(forms.ModelForm):
    class Meta:
        model = ProprietaireProfile
        fields = ['assurance_document', 'carte_grise_document']
        widgets = {
            'assurance_document': forms.ClearableFileInput(attrs={'accept': 'image/*,.pdf'}),
            'carte_grise_document': forms.ClearableFileInput(attrs={'accept': 'image/*,.pdf'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        assurance = cleaned_data.get('assurance_document')
        carte_grise = cleaned_data.get('carte_grise_document')
        
        if not assurance and not carte_grise:
            raise ValidationError("Vous devez fournir au moins un document")
        
        # Validation des fichiers
        for field_name in ['assurance_document', 'carte_grise_document']:
            if field_name in self.files:
                file = self.files[field_name]
                if file.size > 10 * 1024 * 1024:  # 10MB
                    self.add_error(field_name, "La taille du fichier ne doit pas dépasser 10MB")
                if not file.name.lower().endswith(('.png', '.jpg', '.jpeg', '.pdf')):
                    self.add_error(field_name, "Seuls les fichiers PNG, JPG et PDF sont acceptés")
        
        return cleaned_data
        
class PaiementForm(forms.ModelForm):
    class Meta:
        model = Paiement
        fields = ['methode']
        widgets = {
            'methode': forms.RadioSelect(choices=Paiement.METHODES_PAIEMENT)
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['methode'].label = "Méthode de paiement"
        self.fields['methode'].required = True
        
class LoueurPreferencesForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Initialisation de FormHelper
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-3'
        self.helper.field_class = 'col-lg-9'
        
        # Configuration du layout
        self.helper.layout = Layout(
            Fieldset(
                'Préférences générales',
                'preferred_payment_method',
                'driving_experience',
            ),
            Fieldset(
                'Types de véhicules préférés',
                'preferred_vehicle_types',
            ),
            Submit('submit', 'Enregistrer', css_class='btn btn-orange')
        )

    class Meta:
        model = LoueurProfile
        fields = ['preferred_payment_method', 'preferred_vehicle_types', 'driving_experience']
        widgets = {
            'preferred_vehicle_types': forms.CheckboxSelectMultiple(
                choices=Voiture.TYPE_VEHICULE_CHOICES
            ),
            'preferred_payment_method': forms.RadioSelect(
                choices=Paiement.METHODES_PAIEMENT
            ),
            'driving_experience': forms.NumberInput(attrs={
                'min': 1,
                'max': 50,
                'class': 'form-control'
            })
        }

class DrivingLicenseForm(forms.ModelForm):
    class Meta:
        model = LoueurProfile
        fields = ['driving_license', 'license_expiry']
        widgets = {
            'license_expiry': forms.DateInput(attrs={'type': 'date'})
        }
        
class ProprietaireDocumentsForm(forms.ModelForm):
    assurance_document = forms.FileField(
        label="Attestation d'assurance",
        required=False,
        widget=forms.ClearableFileInput(attrs={
            'accept': '.pdf,.jpg,.jpeg,.png',
            'class': 'form-control-file'
        }),
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png'])]
    )
    
    carte_grise_document = forms.FileField(
        label="Carte grise",
        required=False,
        widget=forms.ClearableFileInput(attrs={
            'accept': '.pdf,.jpg,.jpeg,.png',
            'class': 'form-control-file'
        }),
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png'])]
    )

    class Meta:
        model = ProprietaireProfile
        fields = ['assurance_document', 'carte_grise_document']
        error_messages = {
            'assurance_document': {
                'required': "L'attestation d'assurance est obligatoire",
            },
            'carte_grise_document': {
                'required': "La carte grise est obligatoire",
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Personnalisation des messages d'erreur
        for field in self.fields.values():
            field.error_messages = {
                'invalid': "Fichier invalide",
                'required': "Ce document est obligatoire",
                'invalid_extension': "Seuls les formats PDF, JPG, PNG sont acceptés",
            }

    def clean(self):
        cleaned_data = super().clean()
        assurance = cleaned_data.get('assurance_document')
        carte_grise = cleaned_data.get('carte_grise_document')
        
        # Validation de la présence des fichiers
        if not assurance and not carte_grise:
            raise ValidationError(
                "Vous devez fournir au moins un document véhicule (assurance ou carte grise)",
                code='documents_required'
            )
        
        # Validation des fichiers uploadés
        for field_name, file in self.files.items():
            # Validation de la taille
            if file.size > 10 * 1024 * 1024:  # 10MB
                self.add_error(field_name, "Fichier trop volumineux (>10MB)")
            
            # Validation de l'extension (déjà gérée par le validateur)
        
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Ne mettre à jour que si un nouveau fichier est fourni
        for field_name in ['assurance_document', 'carte_grise_document']:
            if field_name in self.changed_data:
                setattr(instance, field_name, self.cleaned_data[field_name])
        
        if commit:
            instance.save()
        return instance
        
class DocumentVerificationForm(forms.ModelForm):
    class Meta:
        model = DocumentVerification
        fields = ['id_card', 'driver_license', 'passport', 'selfie']
        
    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get('driver_license') or not cleaned_data.get('id_card'):
            raise forms.ValidationError("Au moins un document véhicule (permis ou carte d'identité) est requis")
        return cleaned_data


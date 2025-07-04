from django.db import models
from django.db.models import Q
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import MinValueValidator, RegexValidator, FileExtensionValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from django.conf import settings
from django.db import transaction
import uuid

PHONE_VALIDATOR = RegexValidator(
    regex=r'^\+?[0-9]{8,15}$',
    message="Format : +225XXXXXXXX ou 0XXXXXXXX"
)

class UserManager(BaseUserManager):
    def create_user(self, email, username, password=None, **extra_fields):
        if not email:
            raise ValueError('Users must have an email address')
        if not username:
            raise ValueError('Users must have a username')
            
        email = self.normalize_email(email)
        user = self.model(
            email=email,
            username=username,
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        return self.create_user(email, username, password, **extra_fields)
        
class User(AbstractUser):
    objects = UserManager()
    
    TYPE_CHOICES = [
        ('LOUEUR', 'Loueur'),
        ('PROPRIETAIRE', 'Propriétaire'),
        ('ADMIN', 'Administrateur'),
    ]
    
    VERIFICATION_STATUS = [
        ('pending', 'En attente'),
        ('approved', 'Approuvé'),
        ('rejected', 'Rejeté'),
        ('documents_required', 'Documents requis')
    ]
    
    # Champs de base
    user_type = models.CharField(
        max_length=13,
        choices=TYPE_CHOICES,
        default='LOUEUR',
        verbose_name="Type d'utilisateur"
    )
    
    verification_status = models.CharField(
        max_length=20,
        choices=VERIFICATION_STATUS,
        default='documents_required',
        verbose_name="Statut de vérification"
    )
    
    # Informations personnelles
    date_naissance = models.DateField(
        verbose_name="Date de naissance",
        null=True,
        blank=True
    )
    
    phone = models.CharField(
        max_length=20,
        validators=[PHONE_VALIDATOR],
        verbose_name="Téléphone"
    )
    
    # Localisation
    city = models.CharField(max_length=100, verbose_name="Ville")
    country = models.CharField(max_length=2, default='CI', verbose_name="Pays")
    
    # Profil
    photo = models.ImageField(
        upload_to='profiles/',
        blank=True,
        null=True,
        verbose_name="Photo de profil"
    )
    
    # Système de parrainage
    parrain = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        limit_choices_to={'user_type': 'LOUEUR'},
        verbose_name="Parrain"
    )
    
    # Sécurité et vérification
    is_verified = models.BooleanField(default=False, verbose_name="Compte vérifié")
    verification_date = models.DateTimeField(null=True, blank=True)
    
    # Gestion financière
    credit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Crédit disponible (XOF)"
    )
    
    # Système de confiance
    trust_score = models.PositiveSmallIntegerField(
        default=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Score de confiance"
    )
    
    trust_metrics = models.JSONField(
        default=dict,
        verbose_name="Métriques de confiance"
    )
    
    last_trust_update = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"
        ordering = ['-date_joined']
        permissions = [
            ("can_verify_users", "Peut vérifier les utilisateurs"),
            ("can_manage_verifications", "Peut gérer les vérifications"),
        ]

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_user_type_display()})"

    def save(self, *args, **kwargs):
        # Gestion automatique des admins
        if self.is_superuser:
            self.user_type = 'ADMIN'
            self.is_verified = True
            self.verification_status = 'approved'
        
        # Validation cohérente des propriétaires
        if self.user_type == 'PROPRIETAIRE' and self.verification_status == 'approved':
            self.is_verified = True
            self.verification_date = timezone.now()
        
        super().save(*args, **kwargs)

    @property
    def needs_verification(self):
        """Détermine si l'utilisateur a besoin de vérification"""
        return not self.is_verified and self.user_type in ['PROPRIETAIRE', 'LOUEUR']

    @property
    def verification_badge(self):
        """Retourne un badge HTML pour l'admin"""
        from django.utils.html import format_html
        colors = {
            'approved': 'green',
            'rejected': 'red',
            'pending': 'orange',
            'documents_required': 'gray'
        }
        return format_html(
            '<span style="color:{}">{}</span>',
            colors.get(self.verification_status, 'black'),
            self.get_verification_status_display()
        )


class ProprietaireProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='proprietaire_profile',
        verbose_name="Utilisateur"
    )
    
    # Informations légales
    cin = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        verbose_name="Numéro CIN",
        validators=[
            RegexValidator(
                regex=r'^[0-9]{2}[A-Za-z]{1}[0-9]{5}$',
                message="Format : 99X99999 (2 chiffres, 1 lettre, 5 chiffres)"
            )
        ]
    )
    
    address = models.TextField(verbose_name="Adresse complète")
    
    # Documents
    assurance_document = models.FileField(
        upload_to='documents/assurance/%Y/%m/%d/',
        verbose_name="Attestation d'assurance",
        null=True,
        blank=True,
        validators=[FileExtensionValidator(['pdf', 'jpg', 'jpeg', 'png'])],
        help_text="Format PDF, JPG ou PNG (max 10MB)"
    )
    
    carte_grise_document = models.FileField(
        upload_to='documents/carte_grise/%Y/%m/%d/',
        verbose_name="Carte grise",
        null=True,
        blank=True,
        validators=[FileExtensionValidator(['pdf', 'jpg', 'jpeg', 'png'])],
        help_text="Format PDF, JPG ou PNG (max 10MB)"
    )
    
    # Métadonnées
    documents_verified = models.BooleanField(
        default=False,
        verbose_name="Documents vérifiés"
    )
    verification_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date de vérification"
    )
    admin_notes = models.TextField(
        blank=True,
        verbose_name="Notes administratives"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Dernière modification"
    )

    class Meta:
        verbose_name = "Profil Propriétaire"
        verbose_name_plural = "Profils Propriétaires"
        ordering = ['-created_at']
        permissions = [
            ("can_verify_documents", "Peut vérifier les documents"),
            ("can_manage_profiles", "Peut gérer tous les profils"),
        ]

    def __str__(self):
        return f"Profil Propriétaire - {self.user.get_full_name() or self.user.username}"

    def clean(self):
        """Validation des documents"""
        super().clean()
        
        max_size = 10 * 1024 * 1024  # 10MB
        for field_name in ['assurance_document', 'carte_grise_document']:
            file = getattr(self, field_name)
            if file and file.size > max_size:
                raise ValidationError(
                    f"Le fichier {field_name} dépasse 10MB (taille actuelle: {file.size/1024/1024:.1f}MB)"
                )

    def save(self, *args, **kwargs):
        """Mise à jour automatique du statut"""
        self.update_verification_status()
        super().save(*args, **kwargs)

    def update_verification_status(self):
        """Met à jour le statut de vérification"""
        if self.documents_complets:
            self.documents_verified = True
            if not self.verification_date:
                self.verification_date = timezone.now()
            
            if self.user.verification_status != 'approved':
                self.user.verification_status = 'pending'
                self.user.save()
        else:
            self.documents_verified = False
            self.verification_date = None

    @property
    def verification_status(self):
        """Retourne le statut de vérification de l'utilisateur associé"""
        return self.user.get_verification_status_display()

    @property
    def documents_complets(self):
        """Vérifie que tous les documents requis sont présents"""
        return bool(self.assurance_document and self.carte_grise_document)

    @property
    def documents_count(self):
        """Compte les documents présents"""
        return sum([bool(self.assurance_document), bool(self.carte_grise_document)])

    @property
    def documents_status(self):
        """Retourne le statut des documents sous forme de texte"""
        assurance = "✓" if self.assurance_document else "✗"
        carte_grise = "✓" if self.carte_grise_document else "✗"
        return f"Assurance: {assurance} | Carte Grise: {carte_grise}"

    @property
    def documents_status_html(self):
        """Version HTML colorée du statut des documents"""
        from django.utils.html import format_html
        assurance = format_html(
            '<span style="color:{}">{}</span>',
            'green' if self.assurance_document else 'red',
            '✓' if self.assurance_document else '✗'
        )
        carte_grise = format_html(
            '<span style="color:{}">{}</span>',
            'green' if self.carte_grise_document else 'red',
            '✓' if self.carte_grise_document else '✗'
        )
        return format_html("Assurance: {} | Carte Grise: {}", assurance, carte_grise)

    def get_documents_urls(self):
        """Retourne les URLs des documents sous forme de dictionnaire"""
        return {
            'assurance': self.assurance_document.url if self.assurance_document else None,
            'carte_grise': self.carte_grise_document.url if self.carte_grise_document else None
        }

    def get_verification_badge(self):
        """Badge coloré pour le statut de vérification"""
        from django.utils.html import format_html
        status = self.user.verification_status
        colors = {
            'approved': ('green', '✓ Vérifié'),
            'pending': ('orange', '⏳ En attente'),
            'rejected': ('red', '✗ Rejeté'),
            'documents_required': ('gray', '📄 Docs requis')
        }
        color, text = colors.get(status, ('black', 'Inconnu'))
        return format_html(
            '<span style="color:{};font-weight:bold">{}</span>',
            color, text
        )

    def approve(self):
        """Approuve manuellement le profil"""
        self.documents_verified = True
        self.verification_date = timezone.now()
        self.user.verification_status = 'approved'
        self.user.is_verified = True
        self.save()
        self.user.save()
        return True

    def reject(self, reason=""):
        """Rejette le profil"""
        self.documents_verified = False
        self.verification_date = None
        self.admin_notes = reason
        self.user.verification_status = 'rejected'
        self.user.is_verified = False
        self.save()
        self.user.save()
        return True

class Paiement(models.Model):
    METHODES_PAIEMENT = [
        ('ORANGE', 'Orange Money'),
        ('WAVE', 'Wave'),
        ('PAYPAL', 'PayPal'),
        ('CARTE', 'Carte de crédit'),
        ('PORTEFEUILLE', 'Portefeuille virtuel'),
        ('STRIPE', 'Stripe'),
        ('MOBILE_MONEY', 'Mobile Money International')
    ]
    
    STATUT_CHOICES = [
        ('EN_ATTENTE', 'En attente'),
        ('REUSSI', 'Réussi'),
        ('ECHOUE', 'Échoué'),
        ('REMBOURSE', 'Remboursé'),
        ('EN_CONTROLE', 'En contrôle antifraude')
    ]
    
    DEVISE_CHOICES = [
        ('XOF', 'Franc CFA (XOF)'),
        ('EUR', 'Euro (EUR)'),
        ('USD', 'Dollar US (USD)'),
        ('GBP', 'Livre Sterling (GBP)'),
        ('NGN', 'Naira Nigérian (NGN)'),
        ('GHS', 'Cedi Ghanéen (GHS)')
    ]

    # Relations
    reservation = models.ForeignKey(
        'Reservation', 
        on_delete=models.CASCADE,
        related_name='paiements'
    )
    
    # Informations de base
    methode = models.CharField(
        max_length=20, 
        choices=METHODES_PAIEMENT,
        verbose_name="Méthode de paiement"
    )
    montant = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Montant initial"
    )
    
    # Gestion multi-devises
    devise_origine = models.CharField(
        max_length=3,
        choices=DEVISE_CHOICES,
        default='XOF',
        verbose_name="Devise d'origine"
    )
    taux_conversion = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        default=1.0,
        verbose_name="Taux de conversion"
    )
    montant_converti = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Montant en XOF"
    )
    
    # Suivi transaction
    transaction_id = models.CharField(
        max_length=100,
        unique=True,
        blank=True,
        null=True,
        verbose_name="ID Transaction"
    )
    reference = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        verbose_name="Référence interne"
    )
    statut = models.CharField(
        max_length=20,
        choices=STATUT_CHOICES,
        default='EN_ATTENTE',
        verbose_name="Statut"
    )
    
    # Métadonnées
    date_creation = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création"
    )
    date_mise_a_jour = models.DateTimeField(
        auto_now=True,
        verbose_name="Dernière mise à jour"
    )
    date_validation = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date de validation"
    )
    
    # Données techniques
    reponse_api = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Réponse API"
    )
    metadata = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Métadonnées supplémentaires"
    )
    
    # Sécurité
    tentative_fraude = models.BooleanField(
        default=False,
        verbose_name="Tentative de fraude détectée"
    )
    ip_client = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="IP du client"
    )

    class Meta:
        verbose_name = "Paiement"
        verbose_name_plural = "Paiements"
        ordering = ['-date_creation']
        indexes = [
            models.Index(fields=['transaction_id']),
            models.Index(fields=['statut']),
            models.Index(fields=['methode']),
        ]
        permissions = [
            ("refund_payment", "Peut rembourser un paiement"),
            ("view_fraud", "Peut voir les paiements suspects"),
        ]

    def __str__(self):
        return f"Paiement #{self.id} - {self.get_methode_display()} ({self.montant} {self.devise_origine})"

    def save(self, *args, **kwargs):
        """Surcharge de la méthode save pour gérer la conversion automatique"""
        self._handle_currency_conversion()
        self._generate_transaction_id()
        self._update_status_dates()
        super().save(*args, **kwargs)

    def _handle_currency_conversion(self):
        """Gère la conversion automatique des devises"""
        if not self.montant_converti or self._state.adding:
            try:
                from location.services.currency_service import CurrencyService
                self.montant_converti = CurrencyService.convert(
                    self.montant, 
                    self.devise_origine,
                    'XOF'  # Devise de référence
                )
                self.taux_conversion = Decimal(self.montant_converti) / Decimal(self.montant)
            except Exception as e:
                # Fallback en cas d'erreur de conversion
                self.montant_converti = self.montant
                self.taux_conversion = Decimal('1.0')
                self.metadata = {
                    'conversion_error': str(e),
                    'original_amount': float(self.montant)
                }

    def _generate_transaction_id(self):
        """Génère un ID transaction si vide"""
        if not self.transaction_id:
            prefix = {
                'ORANGE': 'OM',
                'WAVE': 'WV',
                'PAYPAL': 'PP',
                'CARTE': 'CC',
                'STRIPE': 'ST',
                'MOBILE_MONEY': 'MM'
            }.get(self.methode, 'TX')
            
            self.transaction_id = f"{prefix}-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

    def _update_status_dates(self):
        """Met à jour les dates de statut"""
        if self.statut == 'REUSSI' and not self.date_validation:
            self.date_validation = timezone.now()
        elif self.statut in ['ECHOUE', 'REMBOURSE']:
            self.date_validation = None

    @property
    def montant_total_xof(self):
        """Retourne le montant total converti en XOF"""
        return self.montant_converti

    @property
    def frais_transaction(self):
        """Calcule les frais de transaction selon la méthode"""
        frais = {
            'ORANGE': Decimal('0.015'),  # 1.5%
            'WAVE': Decimal('0.02'),     # 2%
            'PAYPAL': Decimal('0.05'),  # 5%
            'CARTE': Decimal('0.03'),   # 3%
            'STRIPE': Decimal('0.029') + Decimal('0.30'),  # 2.9% + 0.30€
            'MOBILE_MONEY': Decimal('0.025')  # 2.5%
        }.get(self.methode, Decimal('0.0'))
        
        return self.montant_converti * frais

    def rembourser(self, amount=None):
        """
        Lance un remboursement partiel ou total
        """
        if self.statut != 'REUSSI':
            raise ValueError("Seuls les paiements réussis peuvent être remboursés")
            
        amount = amount or self.montant_converti
        from location.services.payment_service import PaymentService
        result = PaymentService.process_refund(self, amount)
        
        if result['success']:
            self.statut = 'REMBOURSE'
            self.save()
        return result

    def mark_as_fraud(self):
        """Marque le paiement comme frauduleux"""
        self.tentative_fraude = True
        self.statut = 'ECHOUE'
        self.save()
        self._trigger_fraud_analysis()

    def _trigger_fraud_analysis(self):
        """Déclenche une analyse antifraude"""
        from location.tasks import analyze_payment_fraud
        analyze_payment_fraud.delay(self.id)

    def get_payment_url(self):
        """
        Génère l'URL de paiement selon la méthode
        """
        from django.urls import reverse
        methods = {
            'ORANGE': reverse('orange_payment', args=[self.reference]),
            'WAVE': reverse('wave_payment', args=[self.reference]),
            'PAYPAL': reverse('paypal_payment', args=[self.reference]),
            'STRIPE': reverse('stripe_payment', args=[self.reference]),
            'MOBILE_MONEY': reverse('mobile_money_payment', args=[self.reference])
        }
        return methods.get(self.methode, '')
        
class LoueurProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='loueur_profile'
    )
    passport_number = models.CharField(
        max_length=50,
        verbose_name="Numéro de passeport",
        blank=True  # Rendre optionnel
    )
    driving_license = models.CharField(
        max_length=50,
        verbose_name="Permis de conduire",
        blank=True  # Rendre optionnel
    )
    license_expiry = models.DateField(
        verbose_name="Date d'expiration du permis",
        null=True,
        blank=True
    )
    preferred_payment_method = models.CharField(
        max_length=20,
        choices=Paiement.METHODES_PAIEMENT,
        default='ORANGE',
        verbose_name="Méthode de paiement préférée"
    )
    driving_experience = models.PositiveSmallIntegerField(
        verbose_name="Années d'expérience de conduite",
        default=1
    )
    is_verified_driver = models.BooleanField(
        default=False,
        verbose_name="Conducteur vérifié"
    )
    preferred_vehicle_types = models.JSONField(
        default=list,
        verbose_name="Types de véhicules préférés"
    )
    insurance_number = models.CharField(
        max_length=50,
        verbose_name="Numéro d'assurance",
        blank=True
    )

    class Meta:
        verbose_name = "Profil Loueur"
        verbose_name_plural = "Profils Loueurs"
        
    def __str__(self):
        return f"Profil Loueur - {self.user.get_full_name() or self.user.username}"
        
    def get_preferred_vehicle_types_display(self):
        """Convertit le JSON en liste lisible"""
        if not self.preferred_vehicle_types:
            return "Aucune préférence"
        choices = dict(Voiture.TYPE_VEHICULE_CHOICES)
        return ", ".join([choices.get(t, t) for t in self.preferred_vehicle_types])

    @property
    def license_is_valid(self):
        if not self.license_expiry:
            return False
        return self.license_expiry > timezone.now().date()
        
class PageView(models.Model):
    url = models.CharField(max_length=255)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    ip_address = models.GenericIPAddressField()
    referrer = models.CharField(max_length=255, blank=True)
    method = models.CharField(max_length=10, default='GET')
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Page View'
        verbose_name_plural = 'Page Views'

    def __str__(self):
        return f"{self.url} - {self.timestamp}"

class Voiture(models.Model):
    TRANSMISSION_CHOICES = [
        ('A', 'Automatique'),
        ('M', 'Manuelle'),
    ]
    
    TYPE_VEHICULE_CHOICES = [
        ('berline', 'Berline'),
        ('suv', 'SUV/4x4'),
        ('citadine', 'Citadine'),
        ('break', 'Break'),
        ('monospace', 'Monospace'),
        ('cabriolet', 'Cabriolet'),
        ('utilitaire', 'Utilitaire'),
        ('sport', 'Voiture de sport'),
    ]
    
    CARBURANT_CHOICES = [
        ('essence', 'Essence'),
        ('diesel', 'Diesel'),
        ('hybride', 'Hybride'),
        ('electrique', 'Électrique'),
        ('gpl', 'GPL'),
    ]

    # Informations de base
    proprietaire = models.ForeignKey(User, on_delete=models.CASCADE, related_name='voitures')
    marque = models.CharField(max_length=100, verbose_name="Marque")
    modele = models.CharField(max_length=100, verbose_name="Modèle")
    annee = models.PositiveIntegerField(verbose_name="Année", validators=[MinValueValidator(1990)])
    
    # Caractéristiques techniques
    type_vehicule = models.CharField(
        max_length=20,
        choices=TYPE_VEHICULE_CHOICES,
        verbose_name="Type de véhicule"
    )
    transmission = models.CharField(
        max_length=20,
        choices=TRANSMISSION_CHOICES,
        default='M'
    )
    carburant = models.CharField(
        max_length=20,
        choices=CARBURANT_CHOICES,
        verbose_name="Carburant"
    )
    caution_amount = models.PositiveIntegerField(
        verbose_name="Montant de la caution (XOF)",
        default=0,
        validators=[MinValueValidator(0)]
    )
    caution_required = models.BooleanField(
        verbose_name="Caution requise",
        default=False
    )
    kilometrage = models.PositiveIntegerField(
        verbose_name="Kilométrage (km)",
        default=0
    )
    nb_portes = models.PositiveSmallIntegerField(
        verbose_name="Nombre de portes",
        default=5  # Valeur par défaut
    )
    nb_places = models.PositiveSmallIntegerField(
        verbose_name="Nombre de places",
        default=5,  # Valeur par défaut
        validators=[MinValueValidator(1), MaxValueValidator(20)]  # Validation
    )
    
    # Équipements
    climatisation = models.BooleanField(
        default=True,
        verbose_name="Climatisation"
    )
    gps = models.BooleanField(
        default=False,
        verbose_name="GPS"
    )
    siege_bebe = models.BooleanField(
        default=False,
        verbose_name="Siège bébé"
    )
    bluetooth = models.BooleanField(
        default=True,
        verbose_name="Bluetooth"
    )
    disponible = models.BooleanField(
        default=True,
        verbose_name="Disponible"
    )
    
    # Location
    prix_jour = models.PositiveIntegerField(
        verbose_name="Prix journalier (XOF)",
        validators=[MinValueValidator(1000)]
    )
    avec_chauffeur = models.BooleanField(
        default=False,
        verbose_name="Avec chauffeur"
    )
    prix_chauffeur = models.PositiveIntegerField(
        verbose_name="Prix chauffeur/jour (XOF)",
        blank=True,
        null=True
    )
    
    # Localisation
    ville = models.CharField(
        max_length=100,
        verbose_name="Ville"
    )
    
    # Visuel et description
    photo = models.ImageField(
        upload_to='voitures/',
        verbose_name="Photo principale",
        blank=True,
        null=True
    )
    description = models.TextField(
        blank=True,
        verbose_name="Description"
    )
    
    # Métadonnées
    date_creation = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création"
    )
    date_modification = models.DateTimeField(
        auto_now=True,
        verbose_name="Dernière modification"
    )

    class Meta:
        verbose_name = "Véhicule"
        verbose_name_plural = "Véhicules"
        ordering = ['-date_creation']
        indexes = [
            models.Index(fields=['ville']),
            models.Index(fields=['prix_jour']),
        ]
        permissions = [
            ("can_manage_cars", "Peut gérer tous les véhicules"),
            ("can_approve_cars", "Peut approuver les nouveaux véhicules"),
        ]

    def __str__(self):
        return f"{self.marque} {self.modele} ({self.annee})"

    def get_absolute_url(self):
        return reverse('voiture_detail', kwargs={'pk': self.pk})

    def clean(self):
        # Validation de l'année
        if self.annee > (timezone.now().year + 1):
            raise ValidationError("L'année ne peut pas être dans le futur")
        
        # Validation des prix
        if self.prix_jour > 500000:  # Nouveau plafond à 500 000 XOF
            raise ValidationError("Prix journalier trop élevé (max 500 000 XOF)")
            
        if self.avec_chauffeur and not self.prix_chauffeur:
            raise ValidationError("Vous devez spécifier un prix pour le chauffeur")
            
        if self.prix_chauffeur and self.prix_chauffeur > 100000:
            raise ValidationError("Prix du chauffeur trop élevé (max 100 000 XOF/jour)")
            
    @property
    def est_disponible(self):
        """Vérifie la disponibilité actuelle (flag + réservations actives)"""
        today = timezone.now().date()
        return (self.disponible and 
                not self.reservations.filter(
                    date_debut__lte=today,
                    date_fin__gte=today,
                    statut='confirme'
                ).exists())

    def est_disponible_pour_periode(self, date_debut, date_fin):
        """Vérifie la disponibilité pour une période spécifique"""
        return (self.disponible and 
                not self.reservations.filter(
                    date_debut__lt=date_fin,
                    date_fin__gt=date_debut,
                    statut='confirme'
                ).exists())

    @property
    def prix_total(self):
        """Retourne le prix total (voiture + chauffeur si applicable)"""
        if self.avec_chauffeur and self.prix_chauffeur:
            return self.prix_jour + self.prix_chauffeur
        return self.prix_jour
        
    def get_calendrier_disponibilite(self, start_date, end_date):
        """Retourne les jours indisponibles entre deux dates"""
        return self.reservations.filter(
            Q(statut='confirme') & 
            Q(date_debut__lte=end_date) & 
            Q(date_fin__gte=start_date)
        ).values_list('date_debut', 'date_fin')

    def get_prix_dynamique(self, date):
        """Calcule un prix basé sur la saisonnalité"""
        HIGH_SEASON_MONTHS = [6, 7, 8, 12]  # Juin, Juillet, Août, Décembre
        return self.prix_jour * (1.2 if date.month in HIGH_SEASON_MONTHS else 1.0)

class Reservation(models.Model):
    STATUT_CHOICES = [
        ('attente_paiement', 'En attente de paiement'),
        ('confirme', 'Confirmé'),
        ('annule', 'Annulé'),
        ('termine', 'Terminé'),
    ]
    
    statut = models.CharField(
        max_length=20,
        choices=STATUT_CHOICES,
        default='attente_paiement'
    )
    voiture = models.ForeignKey(
        Voiture,
        on_delete=models.CASCADE,
        related_name='reservations'
    )
    client = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='reservations_client'
    )
    date_debut = models.DateField(
        verbose_name="Date de début"
    )
    date_fin = models.DateField(
        verbose_name="Date de fin"
    )
    montant_paye = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Montant payé (XOF)"
    )
    commission_loueur = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        default=10.0,
        verbose_name="Commission loueur (%)"
    )
    frais_service = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Frais de service (XOF)"
    )
    commission_proprietaire = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        default=10.0,
        verbose_name="Commission propriétaire (%)"
    )
    est_payable = models.BooleanField(
        default=True,
        verbose_name="Est payable",
        help_text="Indique si la réservation peut être payée"
    )
    caution_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Caution payée (XOF)",
        default=0
    )
    caution_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'En attente'),
            ('held', 'Retenue'),
            ('refunded', 'Remboursée'),
            ('deducted', 'Retenue (déduite)')
        ],
        default='pending'
    )
    date_creation = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création"
    )
    date_modification = models.DateTimeField(
        auto_now=True,
        verbose_name="Dernière modification"
    )
    montant_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Montant total (XOF)"
    )
    points_attribues = models.BooleanField(
        default=False,
        verbose_name="Points de fidélité attribués"
    )
    avec_livraison = models.BooleanField(default=False)
    adresse_livraison = models.TextField(blank=True)

    class Meta:
        verbose_name = "Réservation"
        verbose_name_plural = "Réservations"
        ordering = ['-date_creation']
        constraints = [
            models.UniqueConstraint(
                fields=['voiture', 'date_debut', 'date_fin'],
                name='reservation_unique',
                condition=models.Q(statut__in=['attente_paiement', 'confirme'])
            )
        ]
        permissions = [
            ("can_manage_reservations", "Peut gérer toutes les réservations"),
            ("can_view_reservation_stats", "Peut voir les statistiques de réservation"),
        ]

    def __str__(self):
        return f"Réservation #{self.id} - {self.voiture}"

    def clean(self):
        if self.date_fin <= self.date_debut:
            raise ValidationError("La date de fin doit être postérieure à la date de début")
        
        if (self.date_fin - self.date_debut).days > 30:
            raise ValidationError("La durée maximale de location est de 30 jours")
            
        if self.commission_loueur < 0 or self.commission_loueur > 100:
            raise ValidationError("Commission loueur doit être entre 0 et 100%")
            
        if self.commission_proprietaire < 0 or self.commission_proprietaire > 100:
            raise ValidationError("Commission propriétaire doit être entre 0 et 100%")

    @property
    def duree(self):
        """Retourne la durée en jours de la réservation"""
        return (self.date_fin - self.date_debut).days

    def get_breakdown_payment(self):
        """Retourne le décomposition du paiement"""
        return {
            'base': self.montant_paye - self.frais_service,
            'frais': self.frais_service,
            'total': self.montant_paye
        }

    @property
    def est_en_cours(self):
        today = timezone.now().date()
        return self.date_debut <= today <= self.date_fin and self.statut == 'confirme'
    
    @property
    def est_payable(self):
        """Détermine si la réservation est encore payable"""
        return (
            self.statut == 'attente_paiement' and
            self.date_debut > timezone.now().date()
        )
        
    @property
    def montant_total(self):
        """Calcule le montant total si non défini, sinon retourne la valeur stockée"""
        if hasattr(self, '_montant_total') and self._montant_total is not None:
            return self._montant_total
        return (self.montant_paye or Decimal(0)) + (self.frais_service or Decimal(0))
        
    @montant_total.setter
    def montant_total(self, value):
        self._montant_total = value
        self.montant_paye = value - (self.frais_service or Decimal(0))    

    def calculer_commissions(self):
        from decimal import Decimal
        total = Decimal(str(self.montant_paye))
        return {
            'commission_loueur': total * (Decimal(str(self.commission_loueur)) / Decimal('100')),
            'commission_proprietaire': total * (Decimal(str(self.commission_proprietaire)) / Decimal('100')),
            'revenu_plateforme': total * (Decimal('0.20')),  # 20% (10% + 10%)
            'montant_proprietaire': total * (Decimal('0.90')),  # 90% du total
            'montant_loueur': total * (Decimal('0.90'))  # 90% du total (si applicable)
        }
        
    def save(self, *args, **kwargs):
        # Si paiement réussi mais statut pas à jour
        if hasattr(self, 'paiement') and self.paiement.statut == 'REUSSI' and self.statut != 'confirme':
            self.statut = 'confirme'
        super().save(*args, **kwargs)

    def generer_facture(self):
        commissions = self.calculer_commissions()
        return {
            'reservation': self,
            'details': {
                'jours_location': self.duree,
                'prix_journalier': Decimal(str(self.voiture.prix_jour)),
                'total_brut': self.montant_paye,
                'deductions': {
                    'commission_loueur': commissions['commission_loueur'],
                    'commission_proprietaire': commissions['commission_proprietaire']
                },
                'net_a_payer': self.montant_paye - commissions['commission_loueur'] - commissions['commission_proprietaire']
            }
        }
        
    def get_status_color(self):
        status_colors = {
            'attente_paiement': 'warning',
            'confirme': 'success',
            'annule': 'danger',
            'termine': 'info'
        }
        return status_colors.get(self.statut, 'secondary')

class DocumentVerification(models.Model):
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('approved', 'Approuvé'),
        ('rejected', 'Rejeté'),
        ('documents_required', 'Documents manquants'),
    ]

    # Relation avec l'utilisateur
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='verification'
    )
    
    # Statut et métadonnées
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    notes = models.TextField(
        blank=True,
        null=True,
        help_text="Notes internes pour l'équipe de vérification"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Documents d'identité (communs à tous)
    id_card = models.FileField(
        upload_to='verifications/ids/',
        null=True,
        blank=True,
        verbose_name="Carte d'identité"
    )
    selfie = models.ImageField(
        upload_to='verifications/selfies/',
        null=True,
        blank=True,
        verbose_name="Selfie de vérification"
    )

    # Documents spécifiques aux propriétaires
    vehicle_insurance = models.FileField(
        upload_to='verifications/assurances/',
        null=True,
        blank=True,
        verbose_name="Attestation d'assurance"
    )
    registration_card = models.FileField(
        upload_to='verifications/cartegrise/',
        null=True,
        blank=True,
        verbose_name="Carte grise"
    )

    # Documents spécifiques aux loueurs
    driver_license = models.FileField(
        upload_to='verifications/permis/',
        null=True,
        blank=True,
        verbose_name="Permis de conduire"
    )
    passport = models.FileField(
        upload_to='verifications/passeports/',
        null=True,
        blank=True,
        verbose_name="Passeport"
    )

    class Meta:
        verbose_name = "Vérification d'identité"
        verbose_name_plural = "Vérifications d'identité"
        ordering = ['-updated_at']

    def __str__(self):
        return f"Vérification de {self.user.username} ({self.get_status_display()})"

    def clean(self):
        """Validation des documents requis selon le type d'utilisateur"""
        super().clean()
        
        if self.user.user_type == 'PROPRIETAIRE':
            if not self.vehicle_insurance and not self.registration_card:
                raise ValidationError({
                    'vehicle_insurance': "Au moins un document véhicule (assurance ou carte grise) est requis",
                    'registration_card': "Au moins un document véhicule (assurance ou carte grise) est requis"
                })
        
        if not self.id_card:
            raise ValidationError({
                'id_card': "La pièce d'identité est obligatoire pour tous les utilisateurs"
            })

    def save(self, *args, **kwargs):
        """Logique de sauvegarde avec validation"""
        self.full_clean()  # Force la validation avant sauvegarde
        super().save(*args, **kwargs)

    def documents_count(self):
        """Compte le nombre de documents uploadés"""
        count = 0
        fields = [
            'id_card', 'vehicle_insurance', 'registration_card',
            'driver_license', 'passport', 'selfie'
        ]
        
        for field in fields:
            if getattr(self, field):
                count += 1
                
        return count

    def get_required_documents(self):
        """Retourne la liste des documents requis selon le type d'utilisateur"""
        required = ['id_card']
        
        if self.user.user_type == 'PROPRIETAIRE':
            required.extend(['vehicle_insurance', 'registration_card'])
        elif self.user.user_type == 'LOUEUR':
            required.extend(['driver_license'])
            
        return required

    def is_complete(self):
        """Vérifie si tous les documents requis sont fournis"""
        required = self.get_required_documents()
        for field in required:
            if not getattr(self, field):
                return False
        return True

    def get_document_urls(self):
        """Retourne les URLs des documents sous forme de dictionnaire"""
        return {
            'id_card': self.id_card.url if self.id_card else None,
            'vehicle_insurance': self.vehicle_insurance.url if self.vehicle_insurance else None,
            'registration_card': self.registration_card.url if self.registration_card else None,
            'driver_license': self.driver_license.url if self.driver_license else None,
            'passport': self.passport.url if self.passport else None,
            'selfie': self.selfie.url if self.selfie else None,
        }

    def approve(self):
        """Approuve la vérification"""
        if not self.is_complete():
            raise ValidationError("Tous les documents requis ne sont pas fournis")
            
        self.status = 'approved'
        self.user.is_verified = True
        self.user.save()
        self.save()
        return True

    def reject(self, reason=None):
        """Rejette la vérification"""
        self.status = 'rejected'
        self.user.is_verified = False
        if reason:
            self.notes = reason
        self.user.save()
        self.save()
        return True

    def request_more_documents(self, message):
        """Demande des documents supplémentaires"""
        self.status = 'documents_required'
        self.notes = message
        self.save()
        return True
        
class Document(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    assurance = models.FileField(upload_to='documents/assurances/')
    carte_grise = models.FileField(upload_to='documents/cartes_grise/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

class Evaluation(models.Model):
    voiture = models.ForeignKey(
        Voiture,
        on_delete=models.CASCADE,
        related_name='evaluations'
    )
    client = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='evaluations'
    )
    reservation = models.ForeignKey(
        'Reservation',
        on_delete=models.CASCADE,
        related_name='evaluations',
        null=True,
        blank=True
    )
    note = models.PositiveSmallIntegerField(
        choices=[(1, '1'), (2, '2'), (3, '3'), (4, '4'), (5, '5')],
        verbose_name="Note"
    )
    commentaire = models.TextField(
        blank=True,
        verbose_name="Commentaire"
    )
    date_creation = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création"
    )

    class Meta:
        verbose_name = "Évaluation"
        verbose_name_plural = "Évaluations"
        unique_together = ('voiture', 'client', 'reservation')
        ordering = ['-date_creation']
        
class EvaluationLoueur(models.Model):
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name='evaluations_loueur'
    )
    evaluateur = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='evaluations_donnees'
    )
    evalue = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='evaluations_recues'
    )
    note = models.PositiveSmallIntegerField(
        choices=[(1, '1'), (2, '2'), (3, '3'), (4, '4'), (5, '5')],
        verbose_name="Note"
    )
    commentaire = models.TextField(
        blank=True,
        verbose_name="Commentaire"
    )
    date_creation = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création"
    )

    class Meta:
        verbose_name = "Évaluation de loueur"
        verbose_name_plural = "Évaluations de loueurs"
        unique_together = ('reservation', 'evaluateur')
        ordering = ['-date_creation']

    def __str__(self):
        return f"Évaluation de {self.evalue} par {self.evaluateur}"

class Favoris(models.Model):
    utilisateur = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='favoris_relation'
    )
    voiture = models.ForeignKey(
        Voiture,
        on_delete=models.CASCADE,
        related_name='favoris_voiture'
    )
    date_ajout = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date d'ajout"
    )

    class Meta:
        verbose_name = "Favori"
        verbose_name_plural = "Favoris"
        unique_together = ('utilisateur', 'voiture')
        ordering = ['-date_ajout']

    def __str__(self):
        return f"{self.voiture} favori de {self.utilisateur}"
        
class Litige(models.Model):
    STATUT_CHOICES = [
        ('ouvert', 'Ouvert'),
        ('en_cours', 'En cours'),
        ('resolu', 'Résolu'),
        ('rejete', 'Rejeté'),
    ]
    
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name='litiges'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='litiges_crees'
    )
    motif = models.TextField(verbose_name="Motif du litige")
    statut = models.CharField(
        max_length=10,
        choices=STATUT_CHOICES,
        default='ouvert',
        verbose_name="Statut"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Dernière modification"
    )
    resolution = models.TextField(
        blank=True,
        verbose_name="Détails de résolution"
    )
    
    class Meta:
        verbose_name = "Litige"
        verbose_name_plural = "Litiges"
        ordering = ['-created_at']

    def __str__(self):
        return f"Litige #{self.id} - {self.reservation}"
        
class VoiturePhoto(models.Model):
    voiture = models.ForeignKey(
        Voiture, 
        on_delete=models.CASCADE, 
        related_name='photos'
    )
    photo = models.ImageField(
        upload_to='voitures/photos/',
        verbose_name="Photo supplémentaire"
    )
    date_ajout = models.DateTimeField(auto_now_add=True)
    est_principale = models.BooleanField(
        default=False,
        verbose_name="Photo principale"
    )

    class Meta:
        verbose_name = "Photo de voiture"
        verbose_name_plural = "Photos de voiture"
        ordering = ['-est_principale', 'date_ajout']

    def __str__(self):
        return f"Photo de {self.voiture.marque} {self.voiture.modele}"
        
class Portefeuille(models.Model):
    proprietaire = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='portefeuille'
    )
    solde = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    
    def crediter(self, montant, reference="", type_transaction="depot"):
        """Crédite le portefeuille de manière atomique"""
        with transaction.atomic():
            self.solde += Decimal(montant)
            self.save()
            return Transaction.objects.create(
                portefeuille=self,
                montant=montant,
                type_transaction=type_transaction,
                statut='valide',
                reference=reference or f"CRD-{timezone.now().timestamp()}"
            )
    
    def debiter(self, montant, reference="", type_transaction="retrait"):
        """Débite le portefeuille de manière atomique avec vérification de solde"""
        if self.solde < Decimal(montant):
            raise ValueError("Solde insuffisant")
        
        with transaction.atomic():
            self.solde -= Decimal(montant)
            self.save()
            return Transaction.objects.create(
                portefeuille=self,
                montant=-Decimal(montant),  # Négatif pour les débits
                type_transaction=type_transaction,
                statut='valide',
                reference=reference or f"DBT-{timezone.now().timestamp()}"
            )

    def __str__(self):
        return f"Portefeuille ({self.proprietaire.username})"

class Transaction(models.Model):
    """Modèle fusionné pour toutes les transactions financières"""
    # Types de transaction (fusion des deux ensembles)
    TYPE_CHOICES = [
        ('depot', 'Dépôt'),
        ('retrait', 'Retrait'),
        ('virement', 'Virement'),
        ('paiement', 'Paiement reçu'),
        ('paiement_service', 'Paiement pour service'),
        ('remboursement', 'Remboursement')
    ]
    
    # Statuts (fusion des deux ensembles)
    STATUT_CHOICES = [
        ('en_attente', 'En attente'),
        ('valide', 'Validé'),
        ('rejete', 'Rejeté'),
        ('annule', 'Annulé'),
        ('completed', 'Complété'),
        ('refunded', 'Remboursé'),
        ('failed', 'Échoué')
    ]
    
    # Méthodes de paiement
    METHODE_CHOICES = [
        ('portefeuille', 'Portefeuille'),
        ('carte', 'Carte bancaire'),
        ('orange', 'Orange Money'),
        ('wave', 'Wave'),
        ('paypal', 'PayPal'),
        ('stripe', 'Stripe')
    ]

    # Champs communs/principaux
    portefeuille = models.ForeignKey(
        'Portefeuille', 
        on_delete=models.CASCADE, 
        related_name='transactions',
        null=True,
        blank=True
    )
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='transactions'
    )
    montant = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=3, default='XOF')
    
    # Informations sur la transaction
    type_transaction = models.CharField(max_length=20, choices=TYPE_CHOICES)
    payment_method = models.CharField(
        max_length=20, 
        choices=METHODE_CHOICES,
        null=True,
        blank=True
    )
    statut = models.CharField(
        max_length=20, 
        choices=STATUT_CHOICES, 
        default='en_attente'
    )
    
    # Références et suivi
    reference = models.CharField(max_length=50, unique=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    # Gestion administrative
    traite_par = models.ForeignKey(
        User, 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL,
        related_name='transactions_traitees'
    )
    motif_rejet = models.TextField(blank=True)
    
    # Horodatages
    date_creation = models.DateTimeField(auto_now_add=True)
    date_traitement = models.DateTimeField(null=True, blank=True)
    date_mise_a_jour = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date_creation']
        verbose_name = "Transaction"
        verbose_name_plural = "Transactions"
        permissions = [
            ("valider_transaction", "Peut valider les transactions"),
            ("annuler_transaction", "Peut annuler les transactions"),
        ]

    def __str__(self):
        return (f"{self.get_type_transaction_display()} - "
                f"{self.montant} {self.currency} - "
                f"{self.user.get_full_name() or self.user.username}")

    def marquer_comme_valide(self, utilisateur):
        self.statut = 'valide'
        self.traite_par = utilisateur
        self.date_traitement = timezone.now()
        self.save()

    def marquer_comme_rejete(self, utilisateur, motif):
        self.statut = 'rejete'
        self.traite_par = utilisateur
        self.motif_rejet = motif
        self.date_traitement = timezone.now()
        self.save()
        
class DrivingHistory(models.Model):
    loueur = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='driving_history'
    )
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    start_date = models.DateField()
    end_date = models.DateField()
    vehicle_model = models.CharField(max_length=100)
    distance_covered = models.PositiveIntegerField(help_text="En kilomètres")
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Historique de conduite"
        verbose_name_plural = "Historiques de conduite"

    def get_caution_display(self):
        if self.caution_required and self.caution_amount > 0:
            return f"{self.caution_amount} XOF"
        return "Aucune"
        

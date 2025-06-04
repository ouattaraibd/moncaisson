from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db import transaction
from django.utils.html import format_html
import json
from django.urls import reverse
from django.utils import timezone
from import_export import resources
from import_export.admin import ImportExportModelAdmin
from .models.core_models import (
    User, ProprietaireProfile, Voiture, Reservation,
    Portefeuille, Transaction, DocumentVerification, LoueurProfile
)
from .models.delivery_models import DeliveryOption, DeliveryRequest
from location.notifications.models import Notification

# Configuration de base
admin.site.site_header = "Administration de MonCaisson"
admin.site.site_title = "Plateforme MonCaisson"
admin.site.index_title = "Accueil de l'administration"
admin.site.register(Notification)

# Ressources pour l'import/export
class VoitureResource(resources.ModelResource):
    class Meta:
        model = Voiture
        fields = ('id', 'marque', 'modele', 'proprietaire__username', 'ville', 'prix_jour')

class ReservationResource(resources.ModelResource):
    class Meta:
        model = Reservation
        fields = ('id', 'voiture__marque', 'client__username', 'date_debut', 'date_fin', 'statut')

# Configuration User complète
@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'user_type', 'is_active', 'is_verified', 
                   'verification_status', 'trust_score', 'date_joined')
    list_filter = ('user_type', 'is_verified', 'verification_status', 'is_active', 'is_staff')
    search_fields = ('username', 'email', 'phone', 'first_name', 'last_name')
    list_editable = ('is_active', 'is_verified')
    actions = ['approve_users', 'reject_users', 'activate_users', 'deactivate_users']
    readonly_fields = ('documents_status', 'proprietaire_link', 'loueur_link', 'date_joined', 'last_login')
    ordering = ('-date_joined',)
    
    fieldsets = (
        (None, {
            'fields': ('username', 'password')
        }),
        ('Informations personnelles', {
            'fields': ('first_name', 'last_name', 'email', 'photo', 'date_naissance')
        }),
        ('Coordonnées', {
            'fields': ('phone', 'city', 'country')
        }),
        ('Statut', {
            'fields': ('user_type', 'is_active', 'is_staff', 'is_superuser')
        }),
        ('Vérification', {
            'fields': ('is_verified', 'verification_status', 'verification_date')
        }),
        ('Système de confiance', {
            'fields': ('trust_score', 'trust_metrics'),
            'classes': ('collapse',)
        }),
        ('Profils associés', {
            'fields': ('proprietaire_link', 'loueur_link'),
            'classes': ('collapse',)
        }),
        ('Historique', {
            'fields': ('date_joined', 'last_login'),
            'classes': ('collapse',)
        }),
    )

    def documents_status(self, obj):
        if obj.user_type == 'PROPRIETAIRE':
            try:
                profile = obj.proprietaire_profile
                docs = []
                if profile.assurance_document:
                    docs.append(f'<a href="{profile.assurance_document.url}" target="_blank">Assurance</a>')
                if profile.carte_grise_document:
                    docs.append(f'<a href="{profile.carte_grise_document.url}" target="_blank">Carte Grise</a>')
                status = "✓ Validé" if profile.documents_verified else "✗ En attente"
                return format_html("{}<br>Statut: {}", " | ".join(docs) if docs else "Aucun document", status)
            except ProprietaireProfile.DoesNotExist:
                return "Profil manquant"
        return "N/A"
    documents_status.short_description = "Documents"

    def proprietaire_link(self, obj):
        if obj.user_type == 'PROPRIETAIRE':
            try:
                url = reverse('admin:location_proprietaireprofile_change', args=[obj.proprietaire_profile.id])
                return format_html('<a href="{}" class="button">Voir profil propriétaire</a>', url)
            except ProprietaireProfile.DoesNotExist:
                return "Profil non créé"
        return "N/A"
    proprietaire_link.short_description = "Profil propriétaire"

    def loueur_link(self, obj):
        if obj.user_type == 'LOUEUR':
            try:
                url = reverse('admin:location_loueurprofile_change', args=[obj.loueur_profile.id])
                return format_html('<a href="{}" class="button">Voir profil loueur</a>', url)
            except LoueurProfile.DoesNotExist:
                return "Profil non créé"
        return "N/A"
    loueur_link.short_description = "Profil loueur"

    @admin.action(description="Approuver les utilisateurs sélectionnés")
    def approve_users(self, request, queryset):
        with transaction.atomic():
            updated = queryset.update(
                is_verified=True,
                verification_status='approved',
                verification_date=timezone.now()
            )
            self.message_user(request, f"{updated} utilisateur(s) approuvé(s)")

    @admin.action(description="Rejeter les utilisateurs sélectionnés")
    def reject_users(self, request, queryset):
        with transaction.atomic():
            updated = queryset.update(
                is_verified=False,
                verification_status='rejected',
                verification_date=None
            )
            self.message_user(request, f"{updated} utilisateur(s) rejeté(s)")

    @admin.action(description="Activer les comptes")
    def activate_users(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} compte(s) activé(s)")

    @admin.action(description="Désactiver les comptes")
    def deactivate_users(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} compte(s) désactivé(s)")


# Configuration ProprietaireProfile
@admin.register(ProprietaireProfile)
class ProprietaireProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'cin', 'documents_status', 'verification_badge')
    list_filter = ('documents_verified', 'user__verification_status')
    search_fields = ('user__username', 'user__email', 'cin', 'address')
    readonly_fields = ('documents_preview', 'verification_status')
    actions = ['approve_profiles', 'reject_profiles', 'verify_documents']
    raw_id_fields = ('user',)

    fieldsets = (
        ('Informations légales', {
            'fields': ('user', 'cin', 'address')
        }),
        ('Documents', {
            'fields': ('assurance_document', 'carte_grise_document', 'documents_preview'),
            'classes': ('collapse',)
        }),
        ('Vérification', {
            'fields': ('documents_verified', 'verification_date', 'admin_notes'),
            'classes': ('collapse',)
        }),
    )

    def documents_status(self, obj):
        assurance = "✓" if obj.assurance_document else "✗"
        carte_grise = "✓" if obj.carte_grise_document else "✗"
        return format_html(
            '<span style="font-family:monospace">Assurance: {} | C.Grise: {}</span>',
            assurance, carte_grise
        )
    documents_status.short_description = "Documents"

    def documents_preview(self, obj):
        previews = []
        if obj.assurance_document:
            previews.append(f"""
                <div style="margin-bottom:20px">
                    <h4>Assurance</h4>
                    <a href="{obj.assurance_document.url}" target="_blank">
                        <img src="{obj.assurance_document.url}" style="max-height:200px;max-width:100%">
                    </a>
                </div>
            """)
        if obj.carte_grise_document:
            previews.append(f"""
                <div style="margin-bottom:20px">
                    <h4>Carte Grise</h4>
                    <a href="{obj.carte_grise_document.url}" target="_blank">
                        <img src="{obj.carte_grise_document.url}" style="max-height:200px;max-width:100%">
                    </a>
                </div>
            """)
        return format_html(''.join(previews)) if previews else "Aucun document"
    documents_preview.short_description = "Prévisualisation"

    def verification_badge(self, obj):
        status = obj.user.verification_status
        colors = {
            'approved': ('green', '✓'),
            'pending': ('orange', '⏳'),
            'rejected': ('red', '✗'),
            'documents_required': ('gray', '📄')
        }
        color, icon = colors.get(status, ('black', '?'))
        return format_html(
            '<span style="color:{};font-weight:bold">{} {}</span>',
            color, icon, obj.user.get_verification_status_display()
        )
    verification_badge.short_description = "Statut"

    @admin.action(description="Approuver les profils")
    def approve_profiles(self, request, queryset):
        with transaction.atomic():
            for profile in queryset:
                profile.documents_verified = True
                profile.verification_date = timezone.now()
                profile.save()
                profile.user.is_verified = True
                profile.user.verification_status = 'approved'
                profile.user.save()
            self.message_user(request, f"{queryset.count()} profil(s) approuvé(s)")

    @admin.action(description="Rejeter les profils")
    def reject_profiles(self, request, queryset):
        with transaction.atomic():
            for profile in queryset:
                profile.documents_verified = False
                profile.verification_date = None
                profile.save()
                profile.user.is_verified = False
                profile.user.verification_status = 'rejected'
                profile.user.save()
            self.message_user(request, f"{queryset.count()} profil(s) rejeté(s)")

    @admin.action(description="Valider les documents")
    def verify_documents(self, request, queryset):
        count = 0
        for profile in queryset:
            if profile.assurance_document and profile.carte_grise_document:
                profile.documents_verified = True
                profile.verification_date = timezone.now()
                profile.save()
                profile.user.is_verified = True
                profile.user.verification_status = 'approved'
                profile.user.save()
                count += 1
        self.message_user(request, f"Documents validés pour {count} propriétaire(s)")


# Configuration LoueurProfile
@admin.register(LoueurProfile)
class LoueurProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'driving_license', 'license_status', 'is_verified_driver')
    list_filter = ('is_verified_driver', 'license_expiry')
    search_fields = ('user__username', 'user__email', 'driving_license', 'passport_number')
    readonly_fields = ('license_status', 'documents_preview')
    actions = ['verify_drivers', 'unverify_drivers']
    raw_id_fields = ('user',)

    fieldsets = (
        ('Informations', {
            'fields': ('user', 'passport_number', 'insurance_number')
        }),
        ('Permis de conduire', {
            'fields': ('driving_license', 'license_expiry', 'license_status', 'driving_experience')
        }),
        ('Vérification', {
            'fields': ('is_verified_driver', 'preferred_payment_method')
        }),
        ('Documents', {
            'fields': ('documents_preview',),
            'classes': ('collapse',)
        }),
    )

    def license_status(self, obj):
        if obj.license_expiry:
            if obj.license_expiry < timezone.now().date():
                return format_html('<span style="color:red">Expiré le {}</span>', obj.license_expiry)
            else:
                return format_html('<span style="color:green">Valide jusqu\'au {}</span>', obj.license_expiry)
        return "Non renseigné"
    license_status.short_description = "Statut du permis"

    def documents_preview(self, obj):
        previews = []
        if hasattr(obj, 'documentverification'):
            dv = obj.documentverification
            if dv.driver_license:
                previews.append(f"""
                    <div style="margin-bottom:20px">
                        <h4>Permis de conduire</h4>
                        <a href="{dv.driver_license.url}" target="_blank">
                            <img src="{dv.driver_license.url}" style="max-height:200px;max-width:100%">
                        </a>
                    </div>
                """)
            if dv.passport:
                previews.append(f"""
                    <div style="margin-bottom:20px">
                        <h4>Passeport</h4>
                        <a href="{dv.passport.url}" target="_blank">
                            <img src="{dv.passport.url}" style="max-height:200px;max-width:100%">
                        </a>
                    </div>
                """)
        return format_html(''.join(previews)) if previews else "Aucun document"
    documents_preview.short_description = "Documents vérifiés"

    @admin.action(description="Valider les conducteurs")
    def verify_drivers(self, request, queryset):
        queryset.update(is_verified_driver=True)
        for profile in queryset:
            profile.user.trust_score = min(100, profile.user.trust_score + 10)
            profile.user.save()
        self.message_user(request, f"{queryset.count()} conducteur(s) validé(s)")

    @admin.action(description="Invalider les conducteurs")
    def unverify_drivers(self, request, queryset):
        queryset.update(is_verified_driver=False)
        for profile in queryset:
            profile.user.trust_score = max(0, profile.user.trust_score - 10)
            profile.user.save()
        self.message_user(request, f"{queryset.count()} conducteur(s) invalidé(s)")



# Configuration Voiture
@admin.register(Voiture)
class VoitureAdmin(ImportExportModelAdmin):
    resource_class = VoitureResource
    list_display = ('marque', 'modele', 'proprietaire', 'ville', 'prix_jour', 'disponible')
    list_filter = ('ville', 'type_vehicule', 'disponible', 'proprietaire__is_verified')
    search_fields = ('marque', 'modele', 'proprietaire__username', 'description')
    raw_id_fields = ('proprietaire',)
    readonly_fields = ('photo_preview',)
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('proprietaire', 'marque', 'modele', 'annee', 'ville', 'description')
        }),
        ('Caractéristiques', {
            'fields': ('type_vehicule', 'transmission', 'carburant', 'kilometrage', 'nb_places', 'nb_portes')
        }),
        ('Équipements', {
            'fields': ('climatisation', 'gps', 'siege_bebe', 'bluetooth'),
            'classes': ('collapse',)
        }),
        ('Tarification', {
            'fields': ('prix_jour', 'avec_chauffeur', 'prix_chauffeur', 'caution_amount', 'caution_required')
        }),
        ('Visuel', {
            'fields': ('photo', 'photo_preview')
        }),
    )

    def photo_preview(self, obj):
        if obj.photo:
            return format_html('<img src="{}" style="max-height:200px;"/>', obj.photo.url)
        return "Aucune photo"
    photo_preview.short_description = "Prévisualisation"

# Configuration Reservation
@admin.register(Reservation)
class ReservationAdmin(ImportExportModelAdmin):
    resource_class = ReservationResource
    list_display = ('id', 'voiture', 'client', 'statut', 'date_debut', 'date_fin', 'montant_total')
    list_filter = ('statut', 'date_debut', 'voiture__proprietaire')
    search_fields = ('voiture__marque', 'client__username', 'id')
    raw_id_fields = ('voiture', 'client')
    readonly_fields = ('montant_breakdown',)

    def montant_breakdown(self, obj):
        return format_html("""
            <table>
                <tr><td>Prix base:</td><td>{:.2f} XOF</td></tr>
                <tr><td>Frais service:</td><td>{:.2f} XOF</td></tr>
                <tr><td>Caution:</td><td>{:.2f} XOF</td></tr>
                <tr><td><strong>Total:</strong></td><td><strong>{:.2f} XOF</strong></td></tr>
            </table>
        """, obj.montant_paye - obj.frais_service, obj.frais_service, obj.caution_paid, obj.montant_paye)
    montant_breakdown.short_description = "Détail du montant"
    
# Configuration DocumentVerification
@admin.register(DocumentVerification)
class DocumentVerificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'user_type', 'status', 'documents_count', 'created_at')
    list_filter = ('status', 'user__user_type')
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('user_link', 'documents_preview', 'created_at', 'updated_at')
    actions = ['approve_verifications', 'reject_verifications', 'request_more_documents']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('user_link', 'status', 'notes')
        }),
        ('Documents', {
            'fields': ('documents_preview',),
            'classes': ('collapse', 'expand')
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def user_type(self, obj):
        return obj.user.get_user_type_display()
    user_type.short_description = "Type d'utilisateur"

    def documents_count(self, obj):
        count = obj.documents_count()
        color = 'green' if count >= (4 if obj.user.user_type == 'LOUEUR' else 3) else 'orange'
        return format_html('<span style="color:{}">{}</span>', color, f"{count} document(s)")
    documents_count.short_description = "Documents"

    def documents_preview(self, obj):
        doc_fields = [
            ('id_card', "Carte d'identité"),
            ('vehicle_insurance', "Attestation d'assurance"),
            ('registration_card', "Carte grise"),
            ('driver_license', "Permis de conduire"),
            ('passport', "Passeport"),
            ('selfie', "Selfie")
        ]
        
        docs = []
        for field, label in doc_fields:
            field_value = getattr(obj, field)
            if field_value:
                docs.append(f"""
                    <div style="margin-bottom:20px; border-bottom:1px solid #eee; padding-bottom:10px;">
                        <h4>{label}</h4>
                        <a href="{field_value.url}" target="_blank" style="display:inline-block; margin-top:5px;">
                            <img src="{field_value.url}" style="max-height:200px; max-width:100%; border:1px solid #ddd;">
                        </a>
                    </div>
                """)
        
        return format_html(''.join(docs)) if docs else "Aucun document uploadé"
    documents_preview.short_description = "Prévisualisation des documents"
    documents_preview.allow_tags = True

    def user_link(self, obj):
        url = reverse('admin:location_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{} ({})</a>', url, obj.user.get_full_name() or obj.user.username, obj.user.email)
    user_link.short_description = "Utilisateur"

    @admin.action(description="Approuver les vérifications sélectionnées")
    def approve_verifications(self, request, queryset):
        with transaction.atomic():
            for verification in queryset:
                if verification.is_complete():
                    verification.approve()
                    self.message_user(request, f"Vérification de {verification.user} approuvée avec succès")
                else:
                    self.message_user(request, f"Impossible d'approuver {verification.user} - Documents incomplets", level='ERROR')
    approve_verifications.allowed_permissions = ('change',)

    @admin.action(description="Rejeter les vérifications sélectionnées")
    def reject_verifications(self, request, queryset):
        with transaction.atomic():
            for verification in queryset:
                verification.reject()
            self.message_user(request, f"{queryset.count()} vérification(s) rejetée(s)")
    reject_verifications.allowed_permissions = ('change',)

    @admin.action(description="Demander des documents supplémentaires")
    def request_more_documents(self, request, queryset):
        with transaction.atomic():
            for verification in queryset:
                verification.request_more_documents("Veuillez fournir les documents manquants")
            self.message_user(request, f"{queryset.count()} demande(s) envoyée(s)")
    request_more_documents.allowed_permissions = ('change',)

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def get_readonly_fields(self, request, obj=None):
        if obj:  # En mode édition
            return self.readonly_fields + ('status',)
        return self.readonly_fields

    def get_actions(self, request):
        actions = super().get_actions(request)
        if not request.user.has_perm('location.change_documentverification'):
            del actions['approve_verifications']
            del actions['reject_verifications']
            del actions['request_more_documents']
        return actions

# Configuration financière
@admin.register(Portefeuille)
class PortefeuilleAdmin(admin.ModelAdmin):
    list_display = ('proprietaire', 'solde_display')
    search_fields = ('proprietaire__username',)
    readonly_fields = ('transaction_history',)
    
    def solde_display(self, obj):
        color = 'green' if obj.solde >= 0 else 'red'
        return format_html('<span style="color:{}">{:.2f} XOF</span>', color, obj.solde)
    solde_display.short_description = "Solde"

    def transaction_history(self, obj):
        transactions = obj.transactions.all().order_by('-date')[:5]
        if not transactions:
            return "Aucune transaction"
        
        rows = []
        for t in transactions:
            color = 'green' if t.montant >= 0 else 'red'
            rows.append(f"""
                <tr>
                    <td>{t.date.strftime('%d/%m/%Y %H:%M')}</td>
                    <td>{t.get_type_transaction_display()}</td>
                    <td style="color:{color}">{t.montant:.2f} XOF</td>
                    <td>{t.get_statut_display()}</td>
                </tr>
            """)
        
        return format_html("""
            <table style="width:100%">
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Type</th>
                        <th>Montant</th>
                        <th>Statut</th>
                    </tr>
                </thead>
                <tbody>
                    {}
                </tbody>
            </table>
        """, ''.join(rows))
    transaction_history.short_description = "Historique récent"

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        'reference',
        'user',
        'portefeuille',
        'montant_display',  # Utilisation de la méthode personnalisée
        'type_transaction', 
        'statut',
        'date_creation',
        'payment_method'
    )
    
    list_filter = (
        'type_transaction', 
        'statut', 
        'payment_method',
        'portefeuille__proprietaire'
    )
    
    search_fields = (
        'reference', 
        'user__username',
        'portefeuille__proprietaire__username'
    )
    
    date_hierarchy = 'date_creation'
    readonly_fields = (
        'date_creation', 
        'date_mise_a_jour',
        'metadata_preview'  # Ajout du champ readonly personnalisé
    )
    
    fieldsets = (
        (None, {
            'fields': (
                'user',
                'portefeuille',
                ('montant', 'currency'),
                'type_transaction',
                'payment_method'
            )
        }),
        ('Statut', {
            'fields': (
                'statut',
                'motif_rejet',
                'traite_par',
                'date_traitement'
            )
        }),
        ('Dates', {
            'fields': (
                'date_creation',
                'date_mise_a_jour'
            )
        }),
        ('Métadonnées', {
            'fields': (
                'reference',
                'metadata_preview',  # Remplacement de metadata par la version preview
                'metadata'  # Gardé pour l'édition mais caché dans le readonly
            )
        })
    )

    def montant_display(self, obj):
        """Affichage coloré du montant"""
        color = 'green' if obj.montant >= 0 else 'red'
        return format_html(
            '<span style="color:{}">{:.2f} {}</span>', 
            color, 
            abs(obj.montant), 
            obj.currency
        )
    montant_display.short_description = "Montant"
    montant_display.admin_order_field = 'montant'

    def metadata_preview(self, obj):
        """Affichage formaté des métadonnées"""
        if not obj.metadata:
            return "Aucune métadonnée"
        return format_html(
            "<pre style='max-height: 200px; overflow: auto;'>{}</pre>", 
            json.dumps(obj.metadata, indent=2, ensure_ascii=False)
        )
    metadata_preview.short_description = "Aperçu des métadonnées"

    def get_fieldsets(self, request, obj=None):
        """Cache le champ metadata brut si en mode visualisation"""
        fieldsets = super().get_fieldsets(request, obj)
        if obj:  # En mode édition
            return fieldsets
        # En mode ajout, on montre le champ metadata normal
        return fieldsets

# Configuration Livraison
@admin.register(DeliveryOption)
class DeliveryOptionAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'is_active')
    list_editable = ('price', 'is_active')
    list_filter = ('is_active',)

@admin.register(DeliveryRequest)
class DeliveryRequestAdmin(admin.ModelAdmin):
    list_display = ('reservation', 'delivery_option', 'status', 'requested_date', 'completed_date')
    list_filter = ('status', 'delivery_option')
    raw_id_fields = ('reservation', 'driver')
    readonly_fields = ('delivery_details',)
    date_hierarchy = 'requested_date'

    def delivery_details(self, obj):
        return format_html("""
            <p><strong>Adresse de prise en charge:</strong> {}</p>
            <p><strong>Adresse de livraison:</strong> {}</p>
            <p><strong>Instructions spéciales:</strong> {}</p>
        """, obj.pickup_address, obj.delivery_address, obj.special_instructions or "Aucune")
    delivery_details.short_description = "Détails de livraison"
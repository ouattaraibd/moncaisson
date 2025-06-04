from django.contrib.auth.decorators import login_required, user_passes_test
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView

# Import des vues d'authentification personnalisées
from location.views.auth_views import (
    accueil,
    connexion,
    deconnexion,
    register_choice,
    register_proprietaire,
    register_loueur,
    upload_documents,
    modifier_profil,
    parrainage,
    mes_filleuls,
    dashboard_redirect
)

from location.views.verification_views import upload_verification
from location.views.reservation_views import (
    reserver_voiture,
    confirmer_reservation,
    annuler_reservation,
    generer_facture,
    mes_reservations,
    reservations_proprietaire,
    reservation_detail
)

from location.views.payment_views import (
    initier_paiement,
    notification_paiement,
    confirmation_paiement,
    recapitulatif_paiement,
    process_paiement,
    paiement_en_attente,
    choisir_methode_paiement,
    paiement_annule,
    FacturePDFView,
    orange_notification
)

from location.views.policy_views import PolicyAcceptanceView
from location.views.voiture_views import (
    ListeVoitures,
    VoitureDetail,
    ajouter_voiture,
    ModifierVoiture,
    RechercheVoitures,
    ajouter_favoris,
    retirer_favoris,
    liste_favoris
)

from location.views.portefeuille_views import (
    demande_retrait,
    historique_transactions,
    valider_transaction
)

from location.views.evaluation_views import (
    ajouter_evaluation,
    evaluer_loueur
)

from location.views.dashboard_views import (
    proprietaire_dashboard,
    loueur_dashboard,
    loueur_driving_history, 
    loueur_preferences, 
    update_license,
    statistiques_proprietaire,
    liste_reservations
)

from location.views.reward_views import BadgeListView, RewardListView, ClaimRewardView
from location.views.delivery_views import DeliveryPDFView

# Import des webhooks
from location.webhooks import (
    orange_webhook,
    wave_webhook,
    paypal_webhook,
    stripe_webhook
)

from location.views.messaging_views import send_message, message_success

urlpatterns = [
    # URLs de base et authentification
    path('', accueil, name='accueil'),
    path('connexion/', connexion, name='connexion'),
    path('deconnexion/', auth_views.LogoutView.as_view(), name='deconnexion'),
    path('register/', register_choice, name='register_choice'),
    path('register/proprietaire/', register_proprietaire, name='register_proprietaire'),
    path('register/loueur/', register_loueur, name='register_loueur'),
    path('register/upload-documents/', upload_documents, name='upload_documents'),
    
    # URLs voitures
    path('voitures/', ListeVoitures.as_view(), name='voitures'),
    path('voiture/<int:pk>/', VoitureDetail.as_view(), name='voiture_detail'),
    path('voiture/ajouter/', ajouter_voiture, name='ajouter_voiture'),
    path('voiture/modifier/<int:pk>/', ModifierVoiture.as_view(), name='modifier_voiture'),
    path('voiture/favoris/<int:pk>/', ajouter_favoris, name='ajouter_favoris'),
    path('voiture/favoris/retirer/<int:pk>/', retirer_favoris, name='retirer_favoris'),
    path('recherche/', RechercheVoitures.as_view(), name='recherche'),
    path('favoris/', liste_favoris, name='liste_favoris'),
   
    # URLs réservations et livraisons
    path('reservation/<int:voiture_id>/', reserver_voiture, name='reserver_voiture'),
    path('reservation/confirmer/<int:pk>/', confirmer_reservation, name='confirmer_reservation'),
    path('reservation/annuler/<int:pk>/', annuler_reservation, name='annuler_reservation'),
    path('mes-reservations/', mes_reservations, name='mes_reservations'),
    path('reservation/<int:reservation_id>/detail/', reservation_detail, name='reservation_detail'),
    path('proprietaire/reservations/', reservations_proprietaire, name='reservations_proprietaire'),
    path('delivery/pdf/', DeliveryPDFView.as_view(), name='delivery_pdf'),
    
    # URLs paiements
    path('paiement/initier/<int:reservation_id>/', initier_paiement, name='initier_paiement'),
    path('paiement/confirmation/<int:reservation_id>/', confirmation_paiement, name='confirmation_paiement'),
    path('paiement/annule/', paiement_annule, name='paiement_annule'),
    path('paiement/recapitulatif/<int:reservation_id>/', recapitulatif_paiement, name='recapitulatif_paiement'),
    path('paiement/process/<int:reservation_id>/', process_paiement, name='process_paiement'),
    path('paiement/notification/', notification_paiement, name='notification_paiement'),
    path('paiement/en-attente/', paiement_en_attente, name='paiement_en_attente'),
    path('paiement/choisir-methode/<int:reservation_id>/', choisir_methode_paiement, name='choisir_methode_paiement'),
    path('orange-money/notification/', orange_notification, name='orange_notification'),
    
    # URLs dashboard
    path('dashboard/', include([
        path('', dashboard_redirect, name='dashboard_redirect'),
        path('proprietaire/', proprietaire_dashboard, name='proprietaire_dashboard'),
        path('loueur/', loueur_dashboard, name='loueur_dashboard'),
        path('loueur/historique-conduite/', loueur_driving_history, name='loueur_driving_history'),
        path('loueur/preferences/', loueur_preferences, name='loueur_preferences'),
        path('loueur/permis/', update_license, name='update_license'),
        path('proprietaire/statistiques/', never_cache(statistiques_proprietaire), name='statistiques'),
        path('proprietaire/reservations/', liste_reservations, name='liste_reservations'),
    ])),
    
    # URLs portefeuille
    path('portefeuille/', include([
        path('retrait/', login_required(demande_retrait), name='demande_retrait'),
        path('historique/', login_required(historique_transactions), name='historique_transactions'),
        path('transactions/<int:transaction_id>/valider/', valider_transaction, name='valider_transaction'),
    ])),
    
    # URLs profil et vérification
    path('profil/modifier/', modifier_profil, name='modifier_profil'),
    path('verification/', upload_verification, name='upload_verification'),
    path('verification/pending/', TemplateView.as_view(template_name='location/auth/verification_pending.html'), name='verification_pending'),
    
    # URLs parrainage
    path('parrainage/', user_passes_test(lambda u: u.user_type == 'LOUEUR')(parrainage), name='parrainage'),
    path('mes-filleuls/', user_passes_test(lambda u: u.user_type == 'LOUEUR')(mes_filleuls), name='mes_filleuls'),
    
    # URLs récompenses
    path('badges/', BadgeListView.as_view(), name='badge_list'),
    path('rewards/', RewardListView.as_view(), name='rewards_list'),
    path('rewards/claim/<int:reward_id>/', ClaimRewardView.as_view(), name='claim_reward'),
    
    # URLs évaluations
    path('voiture/<int:voiture_id>/evaluation/', ajouter_evaluation, name='ajouter_evaluation'),
    path('reservation/<int:reservation_id>/evaluation-loueur/', evaluer_loueur, name='evaluer_loueur'),
    
    # Policies
    path('policies/accept/', PolicyAcceptanceView.as_view(), name='policy_accept'),
    
    # Messagerie et notifications
    path('messagerie/', include([
    path('envoyer/<int:user_id>/', send_message, name='send_message'),
    # Ajoutez ici vos autres URLs de messagerie
    ]), name='messaging'),
    path('notifications/', include('location.notifications.urls')),
    path('messagerie/envoyer/<int:user_id>/', send_message, name='send_message'),
    path('messagerie/success/<int:recipient_id>/', message_success, name='message_success'),
    
    # URLs factures
    path('facture/<int:pk>/', generer_facture, name='generer_facture'),
    path('facture/<int:reservation_id>/pdf/', FacturePDFView.as_view(), name='facture_pdf'),
    
    # Webhooks (CSRF exempt)
    path('webhooks/orange/', csrf_exempt(orange_webhook), name='orange_webhook'),
    path('webhooks/wave/', csrf_exempt(wave_webhook), name='wave_webhook'),
    path('webhooks/paypal/', csrf_exempt(paypal_webhook), name='paypal_webhook'),
    path('webhooks/stripe/', csrf_exempt(stripe_webhook), name='stripe_webhook'),
    
    # Réinitialisation de mot de passe
    path('password_reset/',
         auth_views.PasswordResetView.as_view(
             template_name='registration/password_reset_form.html',
             email_template_name='registration/password_reset_email.html',
             subject_template_name='registration/password_reset_subject.txt'
         ),
         name='password_reset'),
    path('password_reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='registration/password_reset_done.html'
         ),
         name='password_reset_done'),
    path('reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='registration/password_reset_confirm.html'
         ),
         name='password_reset_confirm'),
    path('reset/done/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='registration/password_reset_complete.html'
         ),
         name='password_reset_complete'),
]
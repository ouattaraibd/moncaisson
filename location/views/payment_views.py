import logging
import os
from location.models import Reservation
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from django.shortcuts import render, redirect, get_object_or_404
from location.services.currency_service import CurrencyService
from location.views.exceptions import PaymentInitError
from django.contrib import messages
from django.urls import reverse
from django.conf import settings
from django.views.generic import View
from django.template.loader import render_to_string
from django.core.mail import send_mail
from decimal import Decimal
from django.db import transaction
from django.contrib.auth.decorators import login_required
from django.utils import timezone  
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse, JsonResponse, HttpResponseBadRequest
from django.contrib.auth import get_user_model
from xhtml2pdf import pisa
from io import BytesIO
import requests
import time
import hmac
import hashlib
import json
import stripe
from location.models.core_models import Reservation, Paiement, Portefeuille, Transaction
from location.forms import PaiementForm

# Configuration du logger
logger = logging.getLogger(__name__)

# Initialisation Stripe
stripe.api_key = settings.STRIPE_API_KEY

User = get_user_model()

@login_required
def choisir_methode_paiement(request, reservation_id):
    reservation = get_object_or_404(
        Reservation,
        id=reservation_id,
        client=request.user,
        statut='attente_paiement'
    )
    
    if request.method == 'POST':
        methode = request.POST.get('methode')
        if methode in ['CARTE', 'ORANGE', 'WAVE', 'PAYPAL', 'PORTEFEUILLE']:
            
            # Vérification spécifique pour le portefeuille
            if methode == 'PORTEFEUILLE':
                if not hasattr(request.user, 'portefeuille'):
                    messages.error(request, "Votre portefeuille n'est pas disponible")
                    return redirect('choisir_methode_paiement', reservation_id=reservation.id)
                
                if request.user.portefeuille.solde < reservation.montant_total:
                    messages.error(request, "Solde insuffisant dans votre portefeuille")
                    return redirect('choisir_methode_paiement', reservation_id=reservation.id)
            
            try:
                with transaction.atomic():
                    timestamp = int(time.time())
                    transaction_id = f"{methode}-{reservation.id}-{timestamp}-{request.user.id}"
                    
                    # Création du paiement
                    paiement = Paiement.objects.create(
                        reservation=reservation,
                        methode=methode,
                        montant=reservation.montant_total,
                        statut='REUSSI' if settings.DEBUG else 'EN_ATTENTE',
                        transaction_id=transaction_id
                    )
                    
                    if settings.DEBUG:
                        # Mode test - simulation
                        reservation.statut = 'confirme'
                        reservation.save()
                        messages.success(request, f"Paiement {methode} simulé avec succès (mode test)")
                        return redirect('confirmation_paiement', reservation_id=reservation.id)
                    else:
                        # Mode production
                        if methode == 'PORTEFEUILLE':
                            return process_paiement(request, reservation.id)
                        elif methode == 'CARTE':
                            return initier_paiement_carte(request, reservation)
                        elif methode == 'ORANGE':
                            return initier_orange_money(request, reservation)
                        elif methode == 'WAVE':
                            return initier_wave(request, reservation)
                        elif methode == 'PAYPAL':
                            return initier_paypal(request, reservation)
                            
            except Exception as e:
                logger.error(f"Erreur création paiement: {str(e)}", exc_info=True)
                messages.error(request, f"Erreur lors du traitement du paiement: {str(e)}")
                return redirect('choisir_methode_paiement', reservation_id=reservation.id)
        else:
            messages.error(request, "Méthode de paiement invalide")
            return redirect('choisir_methode_paiement', reservation_id=reservation.id)
    
    context = {
        'reservation': reservation,
        'montant_total': reservation.montant_total,
        'mode_test': settings.DEBUG,
        'portefeuille_disponible': hasattr(request.user, 'portefeuille'),
    }
    
    return render(request, 'location/paiement/choisir_methode.html', context)

@login_required
def initier_paiement(request, reservation_id):
    reservation = get_object_or_404(Reservation, id=reservation_id, client=request.user)
    payment_method = request.POST.get('payment_method')

    try:
        if payment_method == 'carte':
            return initier_paiement_carte(request, reservation)
        elif payment_method == 'orange':
            return initier_orange_money(request, reservation)
        elif payment_method == 'wave':
            return initier_wave(request, reservation)
        else:
            messages.error(request, "Méthode de paiement non valide")
            return redirect('choisir_methode_paiement', reservation_id=reservation.id)
            
    except Exception as e:
        logger.error(f"Erreur initialisation paiement: {str(e)}")
        messages.error(request, f"Erreur lors du paiement: {str(e)}")
        return redirect('recapitulatif_paiement', reservation_id=reservation.id)

def initier_cinetpay(request, reservation):
    """Initialisation spécifique à CinetPay"""
    with transaction.atomic():
        transaction_id = f"RES-{reservation.id}-{int(time.time())}"
        
        paiement = Paiement.objects.create(
            reservation=reservation,
            montant=reservation.montant_total,
            transaction_id=transaction_id,
            statut='initie',
            methode='cinetpay'
        )

        payload = {
            "apikey": settings.CINETPAY_API_KEY,
            "site_id": settings.CINETPAY_SITE_ID,
            "transaction_id": transaction_id,
            "amount": str(reservation.montant_total),
            "currency": "XOF",
            "description": f"Réservation #{reservation.id} - {reservation.voiture.marque} {reservation.voiture.modele}",
            "customer_name": request.user.get_full_name() or request.user.username,
            "customer_phone": request.user.phone,
            "customer_email": request.user.email,
            "notify_url": request.build_absolute_uri(reverse('notification_paiement')),
            "return_url": request.build_absolute_uri(reverse('confirmation_paiement', args=[reservation.id])),
            "metadata": json.dumps({"reservation_id": reservation.id})
        }

        response = requests.post(
            "https://api.cinetpay.com/v2/payment",
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        
        data = response.json()
        if data['code'] != '201':
            raise Exception(f"CinetPay: {data.get('message', 'Erreur inconnue')}")

        paiement.reponse_api = data
        paiement.save()
        return redirect(data['payment_url'])

def initier_orange_money(request, reservation):
    """Paiement via Orange Money"""
    try:
        transaction_id = f"ORANGE-{reservation.id}-{int(time.time())}"
        
        paiement = Paiement.objects.create(
            reservation=reservation,
            montant=reservation.montant_total,
            transaction_id=transaction_id,
            statut='initie',
            methode='orange'
        )

        # Configuration Orange Money
        payload = {
            "merchant_key": settings.ORANGE_MONEY_API_KEY,
            "currency": "XOF",
            "order_id": transaction_id,
            "amount": str(reservation.montant_total),
            "return_url": request.build_absolute_uri(
                reverse('confirmation_paiement', args=[reservation.id])
            ),
            "cancel_url": request.build_absolute_uri(
                reverse('paiement_annule')
            ),
            "notif_url": request.build_absolute_uri(
                reverse('orange_notification')
            ),
            "lang": "fr"
        }

        response = requests.post(
            settings.ORANGE_MONEY_API_URL,
            json=payload,
            headers={"Authorization": f"Bearer {settings.ORANGE_MONEY_API_KEY}"},
            timeout=10
        )
        response.raise_for_status()
        
        data = response.json()
        if data.get('payment_url'):
            paiement.reponse_api = data
            paiement.save()
            return redirect(data['payment_url'])
        else:
            raise Exception("Orange Money n'a pas retourné d'URL de paiement")
            
    except Exception as e:
        raise Exception(f"Erreur Orange Money: {str(e)}")

def initier_wave(request, reservation):
    """Initialisation Wave"""
    with transaction.atomic():
        transaction_id = f"WV-{reservation.id}-{int(time.time())}"
        
        paiement = Paiement.objects.create(
            reservation=reservation,
            montant=reservation.montant_total,
            transaction_id=transaction_id,
            statut='initie',
            methode='wave'
        )

        payload = {
            "amount": str(reservation.montant_total),
            "currency": "XOF",
            "client_reference": transaction_id,
            "error_url": request.build_absolute_uri(reverse('paiement_annule')),
            "success_url": request.build_absolute_uri(reverse('confirmation_paiement', args=[reservation.id])),
            "cancel_url": request.build_absolute_uri(reverse('paiement_annule')),
        }

        response = requests.post(
            settings.WAVE_API_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {settings.WAVE_API_KEY}",
                "Content-Type": "application/json"
            },
            timeout=10
        )
        response.raise_for_status()
        
        data = response.json()
        paiement.reponse_api = data
        paiement.save()
        
        if data.get('url'):
            return redirect(data['url'])
        else:
            raise Exception("Wave n'a pas retourné d'URL de paiement")

def initier_paypal(request, reservation):
    """Initialisation PayPal"""
    with transaction.atomic():
        transaction_id = f"PP-{reservation.id}-{int(time.time())}"
        
        paiement = Paiement.objects.create(
            reservation=reservation,
            montant=reservation.montant_total,
            transaction_id=transaction_id,
            statut='initie',
            methode='paypal'
        )

        payload = {
            "intent": "sale",
            "payer": {"payment_method": "paypal"},
            "transactions": [{
                "amount": {
                    "total": str(reservation.montant_total),
                    "currency": "XOF"
                },
                "description": f"Réservation #{reservation.id}",
                "custom": transaction_id,
                "invoice_number": transaction_id
            }],
            "redirect_urls": {
                "return_url": request.build_absolute_uri(reverse('paypal_execute')),
                "cancel_url": request.build_absolute_uri(reverse('paiement_annule'))
            }
        }

        response = requests.post(
            f"{settings.PAYPAL_API_URL}/v1/payments/payment",
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {get_paypal_access_token()}"
            },
            timeout=10
        )
        response.raise_for_status()
        
        data = response.json()
        paiement.reponse_api = data
        paiement.save()
        
        for link in data.get('links', []):
            if link.get('rel') == 'approval_url':
                return redirect(link['href'])
        
        raise Exception("PayPal n'a pas retourné d'URL d'approbation")

def initier_paiement(request, reservation_id):
    """
    Vue pour initier un paiement avec gestion multi-devises
    Args:
        request: HttpRequest
        reservation_id: ID de la réservation
    Returns:
        HttpResponse: Redirection ou template de paiement
    """
    # Récupération de la réservation avec vérification
    reservation = get_object_or_404(
        Reservation.objects.select_related('voiture', 'client'),
        id=reservation_id,
        client=request.user  # Sécurité: vérif que l'user est bien le client
    )

    # Vérification que la réservation est payable
    if not reservation.est_payable:
        messages.error(request, "Cette réservation n'est plus payable")
        return redirect('mes_reservations')

    context = {
        'reservation': reservation,
        'devises': CurrencyService.SUPPORTED_CURRENCIES.keys()
    }

    try:
        if request.method == 'POST':
            return _handle_payment_post(request, reservation, context)
        return _handle_payment_get(request, reservation, context)
    except PaymentInitError as e:
        logger.error(f"Erreur initiation paiement: {str(e)}")
        messages.error(request, "Erreur lors de l'initialisation du paiement")
        return redirect('reservation_detail', reservation_id=reservation_id)
    except Exception as e:
        logger.critical(f"Erreur critique initiation paiement: {str(e)}", exc_info=True)
        messages.error(request, "Une erreur technique est survenue")
        return redirect('accueil')

def _handle_payment_post(request, reservation, context):
    """Gère la soumission du formulaire de paiement"""
    form = PaymentForm(request.POST)
    
    if not form.is_valid():
        context['form'] = form
        return render(request, 'paiement/initier.html', context)

    try:
        # Conversion du montant si nécessaire
        devise = form.cleaned_data['devise']
        montant_total = _convert_amount_if_needed(
            reservation.montant_total, 
            from_currency='XOF',
            to_currency=devise
        )

        # Création du paiement
        paiement = Paiement(
            reservation=reservation,
            methode=form.cleaned_data['methode'],
            devise_origine=devise,
            montant=montant_total,
            ip_client=_get_client_ip(request),
            metadata={
                'user_agent': request.META.get('HTTP_USER_AGENT'),
                'referrer': request.META.get('HTTP_REFERER')
            }
        )
        paiement.save()

        # Mise à jour de la devise de session
        request.session['devise'] = devise
        request.session.modified = True

        logger.info(f"Paiement {paiement.id} initié par {request.user}")
        return redirect('confirmation_paiement', paiement_id=paiement.id)

    except Exception as e:
        logger.error(f"Erreur création paiement: {str(e)}", exc_info=True)
        raise PaymentInitError(f"Erreur création paiement: {str(e)}")

def _handle_payment_get(request, reservation, context):
    """Gère l'affichage initial du formulaire"""
    devise = request.session.get('devise', 'XOF')
    
    try:
        # Pré-calcul du montant dans la devise de session
        montant_affiche = _convert_amount_if_needed(
            reservation.montant_total,
            from_currency='XOF',
            to_currency=devise
        )
    except Exception as e:
        logger.warning(f"Erreur conversion devise: {str(e)}")
        montant_affiche = reservation.montant_total
        devise = 'XOF'

    context.update({
        'form': PaymentForm(initial={
            'methode': 'STRIPE',  # Méthode par défaut
            'devise': devise
        }),
        'montant_affiche': montant_affiche,
        'devise_affichee': devise
    })
    return render(request, 'paiement/initier.html', context)

def _convert_amount_if_needed(amount, from_currency, to_currency):
    """Convertit un montant si les devises sont différentes"""
    if from_currency == to_currency:
        return amount
    return CurrencyService.convert(amount, from_currency, to_currency)

def _get_client_ip(request):
    """Récupère l'IP réelle du client derrière un proxy éventuel"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    return x_forwarded_for.split(',')[0] if x_forwarded_for else request.META.get('REMOTE_ADDR')

def get_paypal_access_token():
    """Obtenir un token d'accès PayPal"""
    auth = (settings.PAYPAL_CLIENT_ID, settings.PAYPAL_SECRET)
    data = {'grant_type': 'client_credentials'}
    response = requests.post(
        f"{settings.PAYPAL_API_URL}/v1/oauth2/token",
        data=data,
        auth=auth,
        headers={"Accept": "application/json", "Accept-Language": "en_US"}
    )
    response.raise_for_status()
    return response.json()['access_token']

@csrf_exempt
def orange_notification(request):
    """Notification Orange Money"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            transaction_id = data['txnid']
            status = data['status']
            
            paiement = Paiement.objects.get(transaction_id=transaction_id)
            if status == 'SUCCESS':
                paiement.statut = 'reussi'
                paiement.reservation.statut = 'confirme'
            else:
                paiement.statut = 'echoue'
            
            paiement.reponse_api = data
            paiement.reservation.save()
            paiement.save()
            
            return JsonResponse({'status': 'success'})
        except Exception as e:
            logger.error(f"Erreur notification Orange: {str(e)}")
            return JsonResponse({'status': 'error'}, status=400)

@csrf_exempt
def stripe_webhook(request):
    """Webhook Stripe"""
    payload = request.body
    sig_header = request.META['HTTP_STRIPE_SIGNATURE']
    event = None

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        return HttpResponseBadRequest()
    except stripe.error.SignatureVerificationError as e:
        return HttpResponseBadRequest()

    if event['type'] == 'charge.succeeded':
        charge = event['data']['object']
        try:
            paiement = Paiement.objects.get(transaction_id=charge['id'])
            paiement.statut = 'reussi'
            paiement.reservation.statut = 'confirme'
            paiement.reponse_api = charge
            paiement.reservation.save()
            paiement.save()
        except Paiement.DoesNotExist:
            logger.error(f"Paiement Stripe non trouvé: {charge['id']}")

    return HttpResponse(status=200)

@csrf_exempt
def notification_paiement(request):
    """
    Endpoint de notification CinetPay
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            transaction_id = data['transaction_id']
            
            # Vérification avec CinetPay
            verification_url = "https://api.cinetpay.com/v2/payment/check"
            payload = {
                "apikey": settings.CINETPAY_API_KEY,
                "site_id": settings.CINETPAY_SITE_ID,
                "transaction_id": transaction_id
            }
            
            response = requests.post(verification_url, json=payload)
            response.raise_for_status()
            result = response.json()
            
            # Traitement du résultat
            paiement = Paiement.objects.get(transaction_id=transaction_id)
            if result['status'] == 'ACCEPTED':
                paiement.statut = 'reussi'
                paiement.reservation.statut = 'confirme'
                paiement.reservation.save()
            else:
                paiement.statut = 'echoue'
            
            paiement.reponse_api = result
            paiement.save()
            
            return JsonResponse({'status': 'success'})
        
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
def confirmation_paiement(request, reservation_id):
    """
    Affiche la confirmation de paiement et gère:
    - Mise à jour du statut de la réservation
    - Attribution des points de fidélité
    - Notification au propriétaire
    """
    reservation = get_object_or_404(
        Reservation.objects.select_related('voiture', 'client', 'voiture__proprietaire'),
        id=reservation_id,
        client=request.user
    )
    
    # Récupère le dernier paiement associé à cette réservation
    paiement = reservation.paiements.order_by('-date_creation').first()
    
    if paiement and paiement.statut == 'REUSSI' and reservation.statut != 'confirme':
        try:
            with transaction.atomic():
                # 1. Mise à jour du statut de la réservation
                reservation.statut = 'confirme'
                reservation.save()
                
                # 2. Attribution des points de fidélité si pas déjà fait
                if not reservation.points_attribues:
                    profile, created = LoyaltyProfile.objects.get_or_create(
                        user=request.user,
                        defaults={'points': 0, 'level': 'BRONZE'}
                    )
                    
                    points_gagnes = int(reservation.montant_total / 1000)  # 1 point par 1000 XOF
                    profile.points += points_gagnes
                    
                    # Mise à jour du niveau
                    if profile.points >= 2000:
                        profile.level = 'GOLD'
                    elif profile.points >= 500:
                        profile.level = 'SILVER'
                    
                    profile.save()
                    reservation.points_attribues = True
                    reservation.save()
                    
                    messages.success(
                        request,
                        f"Paiement confirmé! {points_gagnes} points acquis. Total: {profile.points} points."
                    )
                
                # 3. Notification au propriétaire
                try:
                    subject = f"Nouvelle réservation #{reservation.id}"
                    message = f"""
                    Nouvelle réservation confirmée pour votre {reservation.voiture.marque} {reservation.voiture.modele}:
                    - Client: {reservation.client.get_full_name() or reservation.client.username}
                    - Période: {reservation.date_debut.strftime('%d/%m/%Y')} au {reservation.date_fin.strftime('%d/%m/%Y')}
                    - Montant: {reservation.montant_total:,} XOF
                    """
                    send_mail(
                        subject,
                        message,
                        settings.DEFAULT_FROM_EMAIL,
                        [reservation.voiture.proprietaire.email],
                        fail_silently=True
                    )
                except Exception as email_error:
                    logger.error(f"Erreur notification email: {str(email_error)}")
                
        except Exception as e:
            logger.error(
                f"Erreur confirmation paiement - Réservation {reservation.id}: {str(e)}",
                exc_info=True
            )
            messages.error(
                request,
                "Une erreur technique est survenue lors de la confirmation. Contactez le support."
            )
    elif paiement and paiement.statut == 'ECHOUE':
        messages.error(
            request,
            "Le paiement a échoué. Veuillez réessayer ou choisir une autre méthode."
        )
        return redirect('choisir_methode_paiement', reservation_id=reservation.id)
    
    context = {
        'reservation': reservation,
        'paiement': paiement,
        'success': paiement and paiement.statut == 'REUSSI',
        'now': timezone.now()
    }
    
    return render(request, 'location/paiement/confirmation_paiement.html', context)
    
@login_required
def recapitulatif_paiement(request, reservation_id):
    reservation = get_object_or_404(Reservation, id=reservation_id, client=request.user)
    
    if reservation.statut != 'attente_paiement':
        messages.warning(request, "Cette réservation a déjà été traitée")
        return redirect('mes_reservations')

    montant_total = Decimal(reservation.montant_paye or 0) + Decimal(reservation.frais_service or 0)

    context = {
        'reservation': reservation,
        'montant_base': reservation.montant_paye,
        'frais_service': reservation.frais_service,
        'montant_total': montant_total,
    }
    return redirect('choisir_methode_paiement', reservation_id=reservation.id)
    
@login_required
@transaction.atomic
def process_paiement(request, reservation_id):
    """
    Version robuste avec gestion des erreurs améliorée
    """
    try:
        reservation = get_object_or_404(
            Reservation, 
            id=reservation_id,
            client=request.user,
            statut='attente_paiement'
        )
        
        # Vérification et création du portefeuille si nécessaire
        if not hasattr(request.user, 'portefeuille'):
            Portefeuille.objects.create(proprietaire=request.user)
            messages.info(request, "Portefeuille créé automatiquement")
        
        # 1. Débiter le client
        transaction_client = request.user.portefeuille.debiter(
            montant=reservation.montant_total,
            reference=f"PAY-{reservation.id}",
            type_transaction="paiement_location"
        )
        
        # 2. Créditer le propriétaire (90%)
        montant_proprio = reservation.montant_total * Decimal('0.9')
        transaction_proprio = reservation.voiture.proprietaire.portefeuille.crediter(
            montant=montant_proprio,
            reference=f"REV-{reservation.id}",
            type_transaction="revenu_location"
        )
        
        # 3. Créditer la plateforme (10%)
        admin_user = User.objects.filter(is_superuser=True).first()
        portefeuille_plateforme, created = Portefeuille.objects.get_or_create(
            proprietaire=admin_user,
            defaults={'solde': 0}
        )
        
        montant_plateforme = reservation.montant_total - montant_proprio
        transaction_plateforme = portefeuille_plateforme.crediter(
            montant=montant_plateforme,
            reference=f"COM-{reservation.id}",
            type_transaction="commission"
        )
        
        # 4. Mettre à jour la réservation
        reservation.statut = 'payee'
        reservation.save()
        
        # 5. Créer un objet Paiement
        Paiement.objects.create(
            reservation=reservation,
            montant=reservation.montant_total,
            methode='portefeuille',
            statut='reussi',
            transaction_id=transaction_client.reference,
            reponse_api={
                'transactions': {
                    'client': str(transaction_client.id),
                    'proprietaire': str(transaction_proprio.id),
                    'plateforme': str(transaction_plateforme.id)
                }
            }
        )
        
        messages.success(request, "Paiement effectué avec succès")
        return redirect('confirmation_paiement', reservation_id=reservation.id)
        
    except ObjectDoesNotExist:
        messages.error(request, "Réservation introuvable")
        return redirect('accueil')
    except ValueError as e:
        messages.error(request, str(e))
        return redirect('recapitulatif_paiement', reservation_id=reservation_id)
    except Exception as e:
        logger.error(f"Erreur paiement: {str(e)}", exc_info=True)
        messages.error(request, "Une erreur technique est survenue")
        return redirect('paiement_en_attente')
        
@login_required
@transaction.atomic
def process_refund(request, reservation_id):
    """
    Traite un remboursement complet:
    - Rembourse 100% au client
    - Débite le propriétaire (90%)
    - Débite la plateforme (10%)
    """
    reservation = get_object_or_404(
        Reservation,
        id=reservation_id,
        statut__in=['annulee', 'refusee'],
        paiement__statut='reussi'
    )
    
    try:
        # 1. Rembourser le client (100%)
        transaction_remboursement = request.user.portefeuille.crediter(
            montant=reservation.montant_total,
            reference=f"REF-{reservation.id}",
            type_transaction="remboursement"
        )
        
        # 2. Débiter le propriétaire (90%)
        montant_proprio = reservation.montant_total * Decimal('0.9')
        reservation.voiture.proprietaire.portefeuille.debiter(
            montant=montant_proprio,
            reference=f"RMB-PROP-{reservation.id}",
            type_transaction="remboursement_proprio"
        )
        
        # 3. Débiter la plateforme (10%)
        montant_plateforme = reservation.montant_total - montant_proprio
        portefeuille_plateforme = Portefeuille.objects.get(
            proprietaire__is_superuser=True
        )
        portefeuille_plateforme.debiter(
            montant=montant_plateforme,
            reference=f"RMB-PLAT-{reservation.id}",
            type_transaction="remboursement_plateforme"
        )
        
        # 4. Mettre à jour la réservation et le paiement
        reservation.paiement.statut = 'rembourse'
        reservation.paiement.save()
        
        messages.success(request, "Remboursement effectué avec succès")
        return redirect('reservation_detail', reservation_id=reservation.id)
        
    except Exception as e:
        messages.error(request, f"Erreur lors du remboursement: {str(e)}")
        return redirect('reservation_detail', reservation_id=reservation.id)
        
def paiement_en_attente(request):
    """Vue pour les paiements en attente"""
    context = {}
    try:
        # Vérifie si l'URL mes_reservations existe
        from django.urls import reverse
        reverse('mes_reservations')
        context['mes_reservations_url'] = 'mes_reservations'
    except:
        context['mes_reservations_url'] = 'accueil'  # Fallback vers la page d'accueil
    
    return render(request, 'location/paiement/en_attente.html', context)

@csrf_exempt
def paypal_execute(request):
    """Exécution du paiement PayPal après approbation"""
    if request.method == 'GET':
        payment_id = request.GET.get('paymentId')
        payer_id = request.GET.get('PayerID')
        
        try:
            paiement = Paiement.objects.get(transaction_id__startswith=f"PP-", reponse_api__id=payment_id)
            
            # Exécution du paiement
            url = f"{settings.PAYPAL_API_URL}/v1/payments/payment/{payment_id}/execute"
            payload = {"payer_id": payer_id}
            response = requests.post(
                url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {get_paypal_access_token()}"
                }
            )
            response.raise_for_status()
            
            data = response.json()
            if data['state'] == 'approved':
                paiement.statut = 'reussi'
                paiement.reservation.statut = 'confirme'
                paiement.reservation.save()
                messages.success(request, "Paiement PayPal effectué avec succès")
            else:
                paiement.statut = 'echoue'
                messages.error(request, "Échec du paiement PayPal")
            
            paiement.reponse_api = data
            paiement.save()
            
            return redirect('confirmation_paiement', reservation_id=paiement.reservation.id)
            
        except Exception as e:
            logger.error(f"Erreur execution PayPal: {str(e)}")
            messages.error(request, "Erreur lors du traitement PayPal")
            return redirect('paiement_en_attente')

@require_GET
def paiement_annule(request):
    """Vue appelée quand un paiement est annulé"""
    reservation_id = request.GET.get('reservation_id')
    if reservation_id:
        messages.warning(request, f"Paiement pour la réservation #{reservation_id} annulé")
        return redirect('choisir_methode_paiement', reservation_id=reservation_id)
    messages.warning(request, "Paiement annulé")
    return redirect('accueil')
    
@csrf_exempt
def paypal_webhook(request):
    """Gestion des notifications PayPal"""
    if request.method == 'POST':
        try:
            # Vérification de la signature PayPal
            auth_token = get_paypal_auth_token()
            transmission_id = request.headers.get('Paypal-Transmission-Id')
            cert_url = request.headers.get('Paypal-Cert-Url')
            signature = request.headers.get('Paypal-Transmission-Sig')
            timestamp = request.headers.get('Paypal-Transmission-Time')
            
            verify_data = {
                "auth_algo": "SHA256withRSA",
                "cert_url": cert_url,
                "transmission_id": transmission_id,
                "transmission_sig": signature,
                "transmission_time": timestamp,
                "webhook_id": settings.PAYPAL_WEBHOOK_ID,
                "webhook_event": request.json()
            }
            
            response = requests.post(
                f"{settings.PAYPAL_API_URL}/v1/notifications/verify-webhook-signature",
                json=verify_data,
                headers={"Authorization": f"Bearer {auth_token}"},
                timeout=5
            )
            response.raise_for_status()
            
            if response.json().get('verification_status') != 'SUCCESS':
                raise ValueError("Signature PayPal invalide")
            
            data = request.json()
            event_type = data.get('event_type')
            
            if event_type == 'PAYMENT.CAPTURE.COMPLETED':
                transaction_id = data.get('resource', {}).get('custom_id')
                if transaction_id:
                    payment = Paiement.objects.get(transaction_id=transaction_id)
                    payment.statut = 'REUSSI'
                    payment.reponse_api = data
                    payment.save()
                    
                    # Mettre à jour la réservation
                    payment.reservation.statut = 'CONFIRME'
                    payment.reservation.save()
            
            return JsonResponse({'status': 'success'})
            
        except Exception as e:
            logger.error(f"Erreur webhook PayPal: {str(e)}")
            return JsonResponse({'status': 'error'}, status=400)
    
    return JsonResponse({'status': 'method not allowed'}, status=405)

def get_paypal_auth_token():
    """Obtient un token d'accès PayPal"""
    response = requests.post(
        f"{settings.PAYPAL_API_URL}/v1/oauth2/token",
        auth=(settings.PAYPAL_CLIENT_ID, settings.PAYPAL_SECRET),
        data={'grant_type': 'client_credentials'},
        headers={'Accept': 'application/json'}
    )
    response.raise_for_status()
    return response.json().get('access_token')
    
@csrf_exempt
def wave_webhook(request):
    """Gestion des notifications Wave"""
    if request.method == 'POST':
        try:
            # Vérification de la signature Wave
            secret = settings.WAVE_WEBHOOK_SECRET.encode()
            signature = request.headers.get('X-Wave-Signature')
            body = request.body
            
            # Calcul de la signature HMAC
            digest = hmac.new(secret, body, hashlib.sha256).hexdigest()
            
            if not hmac.compare_digest(digest, signature):
                raise ValueError("Signature Wave invalide")
            
            data = json.loads(body)
            transaction_id = data.get('client_reference')
            status = data.get('status')
            
            if status == 'completed' and transaction_id:
                payment = Paiement.objects.get(transaction_id=transaction_id)
                payment.statut = 'REUSSI'
                payment.reponse_api = data
                payment.save()
                
                # Mettre à jour la réservation
                payment.reservation.statut = 'CONFIRME'
                payment.reservation.save()
            
            return JsonResponse({'status': 'success'})
            
        except Exception as e:
            logger.error(f"Erreur webhook Wave: {str(e)}")
            return JsonResponse({'status': 'error'}, status=400)
    
    return JsonResponse({'status': 'method not allowed'}, status=405)
    
@login_required
def webhook_paiement(request, methode):
    """
    Endpoint pour les webhooks de paiement
    """
    try:
        if methode == 'stripe':
            payload = request.body
            sig_header = request.META['HTTP_STRIPE_SIGNATURE']
            
            try:
                event = stripe.Webhook.construct_event(
                    payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
                )
            except ValueError as e:
                logger.error(f"Erreur payload Stripe: {str(e)}")
                return HttpResponse(status=400)
            except stripe.error.SignatureVerificationError as e:
                logger.error(f"Erreur signature Stripe: {str(e)}")
                return HttpResponse(status=400)
            
            if event['type'] == 'payment_intent.succeeded':
                payment_intent = event['data']['object']
                transaction_id = payment_intent['id']
                
                try:
                    paiement = Paiement.objects.get(transaction_id=transaction_id)
                    paiement.statut = 'REUSSI'
                    paiement.reponse_api = payment_intent
                    paiement.save()
                    
                    # Déclencher la confirmation automatique
                    return redirect('confirmation_paiement', reservation_id=paiement.reservation.id)
                    
                except Paiement.DoesNotExist:
                    logger.error(f"Paiement Stripe non trouvé: {transaction_id}")
                    return HttpResponse(status=404)
        
        elif methode in ['orange', 'wave', 'paypal']:
            # Implémentation similaire pour les autres processeurs
            pass
            
        return HttpResponse(status=200)
        
    except Exception as e:
        logger.error(f"Erreur webhook {methode}: {str(e)}", exc_info=True)
        return HttpResponse(status=500)

@login_required
def historique_paiements(request):
    """
    Affiche l'historique des paiements de l'utilisateur
    """
    paiements = Paiement.objects.filter(
        reservation__client=request.user
    ).select_related('reservation').order_by('-date_creation')
    
    return render(request, 'location/paiement/historique.html', {
        'paiements': paiements
    })
    
class FacturePDFView(View):
    """
    Vue pour générer des factures PDF avec gestion sécurisée des ressources
    """
    def get(self, request, reservation_id, *args, **kwargs):
        # 1. Récupération de la réservation
        reservation = get_object_or_404(Reservation, id=reservation_id)
        
        # 2. Préparation du contexte
        context = {
            'reservation': reservation,
            'base_url': request.build_absolute_uri('/')[:-1],  # Pour les liens absolus
            'debug_mode': settings.DEBUG
        }
        
        # 3. Rendu du template
        html = render_to_string('location/paiement/facture.html', context)
        
        # 4. Création de la réponse PDF
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'filename="facture_{reservation.id}.pdf"'
        
        # 5. Génération du PDF avec gestion des ressources
        pdf_status = pisa.CreatePDF(
            html,
            dest=response,
            encoding='UTF-8',
            link_callback=self.link_callback
        )
        
        # 6. Gestion des erreurs
        if pdf_status.err:
            if settings.DEBUG:
                # En mode debug, retournez l'HTML pour diagnostiquer
                return HttpResponse(html)
            return HttpResponse(
                'Une erreur est survenue lors de la génération du PDF',
                status=500
            )
        return response
    
    def link_callback(self, uri, rel):
        """
        Callback pour gérer les ressources (images, CSS, polices)
        Bloque toutes les requêtes externes et ne permet que les ressources locales
        """
        # 1. Blocage des URLs externes et data-URI
        if uri.startswith(('http://', 'https://', '//', 'data:')):
            return None
        
        # 2. Conversion des URLs statiques
        if uri.startswith(settings.STATIC_URL):
            path = os.path.join(
                settings.STATIC_ROOT,
                uri.replace(settings.STATIC_URL, ''))
        # 3. Conversion des URLs media
        elif uri.startswith(settings.MEDIA_URL):
            path = os.path.join(
                settings.MEDIA_ROOT,
                uri.replace(settings.MEDIA_URL, ''))
        # 4. Gestion des chemins absolus projet
        else:
            path = os.path.join(settings.BASE_DIR, uri.lstrip('/'))
        
        # 5. Vérification de l'existence du fichier
        if not os.path.exists(path):
            if settings.DEBUG:
                print(f"Ressource introuvable: {path}")
            return None
            
        # 6. Retourne le chemin absolu si tout est OK
        return path

    def get_test_pdf(self):
        """
        Méthode utilitaire pour les tests
        """
        from django.test import RequestFactory
        request = RequestFactory().get('/')
        return self.get(request, reservation_id=1)
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone 
from location.forms import DemandeRetraitForm, ValidationTransactionForm
from django.contrib import messages
from location.models.core_models import Transaction
from ..forms import ValidationTransactionForm
from django.http import Http404
from django.core.mail import send_mail
from django.conf import settings

@login_required
def demande_retrait(request):
    portefeuille = request.user.portefeuille
    
    if request.method == 'POST':
        form = DemandeRetraitForm(request.POST, user=request.user)
        if form.is_valid():
            montant = form.cleaned_data['montant']
            Transaction.objects.create(
                portefeuille=portefeuille,
                montant=-montant,  # Montant négatif pour un retrait
                type_transaction='retrait',
                statut='en_attente',
                reference=f'WDR-{request.user.id}-{timezone.now().timestamp()}'
            )
            return redirect('historique_transactions')
    else:
        form = DemandeRetraitForm(user=request.user)
    
    return render(request, 'location/portefeuille/demande_retrait.html', {
        'form': form,
        'solde': portefeuille.solde
    })

@login_required
def historique_transactions(request):
    portefeuille = request.user.portefeuille
    transactions = portefeuille.transactions.all().order_by('-date')
    
    # Pagination
    paginator = Paginator(transactions, 10)  # 10 transactions par page
    page_number = request.GET.get('page')
    
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    
    return render(request, 'location/portefeuille/historique.html', {
        'page_obj': page_obj
    })
    
@login_required
def traiter_retrait(request, transaction_id):
    if not request.user.is_superuser:
        raise PermissionDenied
    
    transaction = get_object_or_404(Transaction, id=transaction_id, type_transaction='retrait')
    
    if request.method == 'POST':
        # Appel API bancaire ou service de paiement
        if paiement_reussi := process_paiement_om(transaction):
            transaction.statut = 'complete'
            transaction.save()
            
            # Notification
            send_mail(
                "Retrait effectué",
                f"Votre retrait de {abs(transaction.montant)} XOF a été traité.",
                settings.DEFAULT_FROM_EMAIL,
                [transaction.portefeuille.proprietaire.email]
            )
            return redirect('admin:location_transaction_changelist')
    
    return render(request, 'admin/traiter_retrait.html', {'transaction': transaction})
    
@login_required
@permission_required('location.valider_transaction', raise_exception=True)
def valider_transaction(request, transaction_id):
    transaction = get_object_or_404(Transaction, id=transaction_id)
    
    if request.method == 'POST':
        form = ValidationTransactionForm(request.POST)
        if form.is_valid():
            action = form.cleaned_data['action']
            
            try:
                with transaction.atomic():
                    if action == 'valider':
                        if transaction.type_transaction == 'retrait':
                            if transaction.portefeuille.solde >= abs(transaction.montant):
                                transaction.portefeuille.solde += transaction.montant  # montant est négatif pour les retraits
                                transaction.portefeuille.save()
                                transaction.statut = 'valide'
                                messages.success(request, "Retrait validé avec succès")
                            else:
                                messages.error(request, "Solde insuffisant pour ce retrait")
                                return redirect('historique_transactions')
                        else:
                            transaction.statut = 'valide'
                            messages.success(request, "Transaction validée avec succès")
                    
                    elif action == 'rejeter':
                        transaction.statut = 'rejete'
                        transaction.motif_rejet = form.cleaned_data['motif_rejet']
                        messages.warning(request, "Transaction rejetée")
                    
                    transaction.traite_par = request.user
                    transaction.date_traitement = timezone.now()
                    transaction.save()
                    
                    return redirect('historique_transactions')
            except Exception as e:
                messages.error(request, f"Une erreur est survenue: {str(e)}")
    else:
        form = ValidationTransactionForm()
    
    return render(request, 'location/portefeuille/valider_transaction.html', {
        'transaction': transaction,
        'form': form
    })
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.utils.safestring import mark_safe
from location.models import DocumentVerification, ProprietaireProfile 
from location.forms import VerificationForm, DocumentsForm

@login_required
def upload_verification(request):
    """
    Vue pour la vérification d'identité générale (documents d'identité)
    """
    # Vérification si l'utilisateur est déjà vérifié
    if hasattr(request.user, 'verification') and request.user.verification.status == 'approuve':
        if request.user.user_type == 'PROPRIETAIRE':
            return redirect('proprietaire_dashboard')
        return redirect('loueur_dashboard')

    # Créer le profil si inexistant (pour propriétaires)
    if request.user.user_type == 'PROPRIETAIRE' and not hasattr(request.user, 'proprietaire_profile'):
        ProprietaireProfile.objects.create(user=request.user)
    
    verification, created = DocumentVerification.objects.get_or_create(
        user=request.user,
        defaults={'status': 'en_attente'}
    )

    if request.method == 'POST':
        form = VerificationForm(request.POST, request.FILES, instance=verification, user=request.user)
        if form.is_valid():
            verification = form.save(commit=False)
            verification.status = 'en_attente'
            verification.save()
            
            messages.success(request, "Documents soumis avec succès! Vérification en cours.")
            return redirect('upload_verification')
    else:
        form = VerificationForm(instance=verification, user=request.user)

    context = {
        'form': form,
        'is_proprietaire': request.user.user_type == 'PROPRIETAIRE',
        'verification_pending': verification.status == 'en_attente',
        'documents_missing': verification.status != 'approuve' and  # Nouvelle condition
                           (not hasattr(request.user, 'proprietaire_profile') or 
                           not request.user.proprietaire_profile.assurance_document or
                           not request.user.proprietaire_profile.carte_grise_document)
    }
    return render(request, 'location/auth/verification.html', context)

@login_required
def upload_documents(request):
    if not hasattr(request.user, 'proprietaire_profile'):
        messages.error(request, "Réservé aux propriétaires")
        return redirect('accueil')

    profile = request.user.proprietaire_profile

    if request.method == 'POST':
        form = ProprietaireDocumentsForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Documents enregistrés! Vérification en cours.")
            return redirect('proprietaire_dashboard')
    else:
        form = ProprietaireDocumentsForm(instance=profile)

    return render(request, 'location/auth/upload_documents.html', {
        'form': form,
        'missing_docs': not (profile.assurance_document and profile.carte_grise_document)
    })


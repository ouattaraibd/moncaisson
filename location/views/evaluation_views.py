from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from location.models import Evaluation, Voiture, Reservation, EvaluationLoueur
from location.forms import EvaluationForm, EvaluationLoueurForm

@login_required
def ajouter_evaluation(request, voiture_id):
    voiture = get_object_or_404(Voiture, id=voiture_id)
    
    # Vérifie si l'utilisateur a une réservation terminée pour cette voiture
    reservation = Reservation.objects.filter(
        voiture=voiture,
        client=request.user,
        statut='termine'
    ).first()

    if not reservation:
        messages.error(request, "Vous ne pouvez évaluer que les voitures que vous avez louées et seulement après la fin de la location")
        return redirect('voiture_detail', pk=voiture_id)

    existing_eval = Evaluation.objects.filter(voiture=voiture, client=request.user).first()
    
    if request.method == 'POST':
        form = EvaluationForm(request.POST, instance=existing_eval)
        if form.is_valid():
            evaluation = form.save(commit=False)
            evaluation.voiture = voiture
            evaluation.client = request.user
            evaluation.reservation = reservation
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

@login_required
def evaluer_loueur(request, reservation_id):
    reservation = get_object_or_404(Reservation, id=reservation_id)
    
    # Vérifications de sécurité
    if reservation.voiture.proprietaire != request.user:
        messages.error(request, "Vous n'êtes pas autorisé à évaluer ce loueur")
        return redirect('reservation_detail', reservation_id=reservation_id)
    
    if reservation.statut != 'termine':
        messages.error(request, "Vous ne pouvez évaluer le loueur qu'après la fin de la location")
        return redirect('reservation_detail', reservation_id=reservation_id)

    existing_eval = EvaluationLoueur.objects.filter(reservation=reservation).first()
    
    if request.method == 'POST':
        form = EvaluationLoueurForm(request.POST, instance=existing_eval)
        if form.is_valid():
            evaluation = form.save(commit=False)
            evaluation.reservation = reservation
            evaluation.evaluateur = request.user
            evaluation.evalue = reservation.client
            evaluation.save()
            messages.success(request, "Évaluation du loueur enregistrée")
            return redirect('reservation_detail', reservation_id=reservation_id)
    else:
        form = EvaluationLoueurForm(instance=existing_eval)
    
    return render(request, 'location/partials/evaluation_loueur_form.html', {
        'form': form,
        'reservation': reservation
    })


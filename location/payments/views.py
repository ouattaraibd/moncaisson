from django.conf import settings
import stripe
stripe.api_key = settings.STRIPE_API_KEY  # Doit exister dans settings.py

# Remplacer la vue initier_paiement_carte par :
def initier_paiement_carte(request, reservation):
    try:
        intent = stripe.PaymentIntent.create(
            amount=int(reservation.montant_total),
            currency='xof',
            payment_method_types=['card'],
            metadata={
                'reservation_id': reservation.id,
                'user_id': request.user.id
            }
        )
        return redirect('confirmation_paiement', reservation_id=reservation.id)
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {str(e)}")
        messages.error(request, "Erreur lors du paiement par carte")
        return redirect('choisir_methode_paiement', reservation_id=reservation.id)


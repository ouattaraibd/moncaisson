import stripe
from django.conf import settings

stripe.api_key = settings.STRIPE_SECRET_KEY_CI  # Clé spécifique Côte d'Ivoire

def create_stripe_charge(amount, currency, email, token):
    """
    amount: en centimes (ex: 10000 = 100€)
    currency: 'eur', 'usd', 'xof'
    token: from Stripe.js
    """
    try:
        charge = stripe.Charge.create(
            amount=amount,
            currency=currency,
            source=token,
            description=f"Location voiture CI - {email}",
            receipt_email=email,
            metadata={"pays": "CI"}
        )
        return charge['id']
    except stripe.error.StripeError as e:
        # Log l'erreur pour analyse fraude
        from sentry_sdk import capture_message
        capture_message(f"Erreur Stripe: {e.user_message}")
        raise


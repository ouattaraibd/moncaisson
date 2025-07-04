import requests
from django.conf import settings

class OrangeMoneyCI:
    def __init__(self):
        self.auth_token = self._get_auth_token()

    def _get_auth_token(self):
        response = requests.post(
            "https://api.orange.com/oauth/v2/token",
            auth=(settings.OM_CLIENT_ID, settings.OM_CLIENT_SECRET),
            data={"grant_type": "client_credentials"},
            timeout=10  # Ajouter un timeout de 10 secondes
        )
        return response.json()['access_token']

    def process_payment(self, phone, amount, reference):
        headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "merchant_key": settings.OM_MERCHANT_KEY,
            "currency": "XOF",
            "order_id": reference,
            "amount": amount,
            "return_url": "https://yourdomain.com/payment/confirm",
            "cancel_url": "https://yourdomain.com/payment/cancel",
            "notif_url": "https://yourdomain.com/api/om/notify",
            "lang": "fr",
            "phone_number": phone
        }
        response = requests.post(
            "https://api.orange.com/orange-money-webpay/ci/v1/webpayment",
            json=payload,
            headers=headers,
            timeout=10
        )
        return response.json()['payment_url']  # Redirigez l'utilisateur ici


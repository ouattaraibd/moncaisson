from django.utils.deprecation import MiddlewareMixin

class CurrencyMiddleware(MiddlewareMixin):
    CURRENCY_CHOICES = ['XOF', 'EUR', 'USD']
    DEFAULT_CURRENCY = 'XOF'
    
    def process_request(self, request):
        # 1. Vérifier la session
        currency = request.session.get('currency')
        
        # 2. Vérifier les paramètres GET
        if 'currency' in request.GET and request.GET['currency'] in self.CURRENCY_CHOICES:
            currency = request.GET['currency']
            request.session['currency'] = currency
            
        # 3. Vérifier l'en-tête Accept-Language
        if not currency:
            lang = request.META.get('HTTP_ACCEPT_LANGUAGE', '')[:2].upper()
            currency = 'EUR' if lang in ['FR', 'DE'] else self.DEFAULT_CURRENCY
            
        # 4. Définir la valeur par défaut
        request.currency = currency or self.DEFAULT_CURRENCY
        
        # 5. Ajouter le taux de change
        request.exchange_rates = self.get_exchange_rates()

    def get_exchange_rates(self):
        # Implémentez une connexion à une API comme fixer.io
        return {
            'XOF': 1,
            'EUR': 655.957,
            'USD': 600.50
        }
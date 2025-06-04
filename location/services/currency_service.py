from decimal import Decimal, InvalidOperation
from django.core.cache import cache
from django.conf import settings
import requests
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class CurrencyService:
    """
    Service complet de gestion des conversions de devises avec :
    - Cache intelligent
    - Fallback à une API secondaire
    - Gestion robuste des erreurs
    - Historique des taux
    """
    
    # Devises supportées avec leurs libellés complets
    SUPPORTED_CURRENCIES = {
        'XOF': {'name': 'Franc CFA Ouest Africain', 'symbol': 'CFA'},
        'EUR': {'name': 'Euro', 'symbol': '€'},
        'USD': {'name': 'Dollar US', 'symbol': '$'},
        'GBP': {'name': 'Livre Sterling', 'symbol': '£'},
        'NGN': {'name': 'Naira Nigérian', 'symbol': '₦'},
        'GHS': {'name': 'Cedi Ghanéen', 'symbol': 'GH₵'}
    }

    @classmethod
    def get_rates(cls, force_update=False):
        """
        Récupère les taux de change avec cache et fallback
        Args:
            force_update (bool): Force une mise à jour des taux
        Returns:
            dict: Dictionnaire des taux {devise: taux}
        """
        cache_key = 'currency_rates_v2'
        rates = None if force_update else cache.get(cache_key)
        
        if not rates:
            try:
                rates = cls._fetch_rates()
                cache.set(cache_key, rates, timeout=3600)  # 1 heure de cache
                cls._save_rates_history(rates)  # Sauvegarde historique
            except RatesNotAvailableError as e:
                logger.warning(f"Erreur forex_python: {str(e)}")
                rates = cache.get(cache_key, cls._get_fallback_rates())
        
        return rates

    @classmethod
    def _fetch_rates(cls):
        """Récupère les taux depuis forex_python avec vérification"""
        c = CurrencyRates()
        base_currency = 'XOF'
        
        rates = {
            'EUR': 1 / c.get_rate(base_currency, 'EUR'),
            'USD': 1 / c.get_rate(base_currency, 'USD'),
            'GBP': 1 / c.get_rate(base_currency, 'GBP'),
            'NGN': c.get_rate('NGN', base_currency),
            'GHS': c.get_rate('GHS', base_currency),
            'XOF': 1.0  # Taux de référence
        }
        
        # Vérification de la cohérence des taux
        if any(rate <= 0 for rate in rates.values()):
            raise RatesNotAvailableError("Taux de change invalides obtenus")
            
        return rates

    @classmethod
    def _get_fallback_rates(cls):
        """Fallback à une API externe si forex_python échoue"""
        try:
            response = requests.get(
                'https://api.exchangerate-api.com/v4/latest/XOF',
                timeout=3
            )
            data = response.json()
            return {
                'EUR': data['rates']['EUR'],
                'USD': data['rates']['USD'],
                'GBP': data['rates']['GBP'],
                'XOF': 1.0
            }
        except Exception as e:
            logger.error(f"Erreur API fallback: {str(e)}")
            return settings.DEFAULT_CURRENCY_RATES  # Valeurs par défaut dans settings.py

    @classmethod
    def _save_rates_history(cls, rates):
        """Sauvegarde l'historique des taux pour analyse"""
        from django.utils import timezone
        from location.models import CurrencyRateHistory  # Modèle à créer
        
        try:
            CurrencyRateHistory.objects.create(
                rates=rates,
                date=timezone.now()
            )
        except Exception as e:
            logger.error(f"Erreur sauvegarde historique: {str(e)}")

    @classmethod
    def convert(cls, amount, from_currency, to_currency='XOF', round_result=True):
        """
        Convertit un montant d'une devise à une autre
        Args:
            amount (float/str/Decimal): Montant à convertir
            from_currency (str): Devise source (code ISO 3 lettres)
            to_currency (str): Devise cible (défaut: XOF)
            round_result (bool): Arrondir le résultat à 2 décimales
        Returns:
            Decimal: Montant converti
        Raises:
            ValueError: Si devise non supportée ou montant invalide
        """
        # Validation des devises
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()
        
        if from_currency not in cls.SUPPORTED_CURRENCIES:
            raise ValueError(f"Devise source non supportée: {from_currency}")
        if to_currency not in cls.SUPPORTED_CURRENCIES:
            raise ValueError(f"Devise cible non supportée: {to_currency}")
        
        # Conversion du montant en Decimal
        try:
            amount = Decimal(str(amount))
        except InvalidOperation:
            raise ValueError("Montant invalide pour la conversion")
        
        # Conversion directe si même devise
        if from_currency == to_currency:
            return amount.quantize(Decimal('0.01')) if round_result else amount
        
        # Récupération des taux
        rates = cls.get_rates()
        from_rate = rates.get(from_currency)
        to_rate = rates.get(to_currency)
        
        if None in (from_rate, to_rate):
            raise ValueError("Taux de change non disponibles pour la paire de devises")
        
        # Calcul de la conversion
        try:
            converted = (amount / from_rate) * to_rate
            return converted.quantize(Decimal('0.01')) if round_result else converted
        except Exception as e:
            logger.error(f"Erreur conversion: {amount} {from_currency}->{to_currency}: {str(e)}")
            raise ValueError("Erreur lors de la conversion des devises")

    @classmethod
    def format_currency(cls, amount, currency_code):
        """
        Formate un montant selon les conventions de la devise
        Args:
            amount (Decimal): Montant à formater
            currency_code (str): Code devise (ISO 3 lettres)
        Returns:
            str: Montant formaté (ex: "500,00 €")
        """
        currency = cls.SUPPORTED_CURRENCIES.get(currency_code.upper())
        if not currency:
            raise ValueError("Devise non supportée pour le formatage")
        
        try:
            amount = Decimal(str(amount))
            formatted = f"{amount:,.2f}".replace(",", " ").replace(".", ",")
            
            if currency_code == 'XOF':
                return f"{formatted} {currency['symbol']}"
            return f"{currency['symbol']} {formatted}"
        except Exception as e:
            logger.error(f"Erreur formatage: {str(e)}")
            return f"{amount} {currency_code}"
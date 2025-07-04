from datetime import datetime

class PricingService:
    @staticmethod
    def calculate_dynamic_price(base_price, date):
        # Implémentez votre logique de pricing ici
        return base_price * 1.2 if date.month in [6,7,8] else base_price


from django.db import transaction
from location.models import DeliveryRequest

class DeliveryService:
    @staticmethod
    def create_delivery(reservation):
        """Crée une demande de livraison"""
        with transaction.atomic():
            return DeliveryRequest.objects.create(
                reservation=reservation,
                status='PENDING',
                delivery_address=reservation.adresse_livraison
            )
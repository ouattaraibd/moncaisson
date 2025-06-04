from django.db.models.signals import post_save
from location.models import Reservation
from location.notifications.models import Notification

def create_reservation_notification(sender, instance, created, **kwargs):
    if created:
        Notification.objects.create(
            user=instance.voiture.proprietaire,
            message=f"Nouvelle réservation #{instance.id}",
            link=f"/reservations/{instance.id}",
            category="reservation"
        )

post_save.connect(create_reservation_notification, sender=Reservation)
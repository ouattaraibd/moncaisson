from django.db import models
from django.core.validators import MinValueValidator
from .core_models import Reservation, User, Voiture
from django.utils.translation import gettext_lazy as _
from .core_models import Reservation, User

class DeliveryOption(models.Model):
    DELIVERY_TYPES = [
        ('STANDARD', _('Standard')),
        ('EXPRESS', _('Express')),
        ('PREMIUM', _('Premium')),
        ('WITH_DRIVER', _('Avec chauffeur'))
    ]
    
    name = models.CharField(
        max_length=100,
        verbose_name=_("Nom de l'option")
    )
    delivery_type = models.CharField(
        max_length=20,
        choices=DELIVERY_TYPES,
        verbose_name=_("Type de livraison"),
        default='STANDARD'
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_("Prix (XOF)"),
        validators=[MinValueValidator(0)]
    )
    description = models.TextField(
        blank=True,
        verbose_name=_("Description")
    )
    available = models.BooleanField(
        default=True,
        verbose_name=_("Disponible")
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Active")
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Date de création")
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Dernière mise à jour")
    )

    class Meta:
        verbose_name = _("Option de livraison")
        verbose_name_plural = _("Options de livraison")
        ordering = ['price']
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'delivery_type'],
                name='unique_delivery_option'
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.get_delivery_type_display()}) - {self.price} XOF"

class DeliveryRequest(models.Model):
    STATUS_CHOICES = [
        ('PENDING', _('En attente')),
        ('ACCEPTED', _('Acceptée')),
        ('IN_PROGRESS', _('En cours')),
        ('COMPLETED', _('Terminée')),
        ('CANCELLED', _('Annulée')),
        ('FAILED', _('Échouée'))
    ]
    
    reservation = models.OneToOneField(
        Reservation,
        on_delete=models.CASCADE,
        related_name='delivery',
        verbose_name=_("Réservation associée")
    )
    delivery_option = models.ForeignKey(
        DeliveryOption,
        on_delete=models.PROTECT,
        verbose_name=_("Option de livraison")
    )
    delivery_address = models.TextField(
        verbose_name=_("Adresse de livraison")
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        verbose_name=_("Statut")
    )
    requested_date = models.DateTimeField(
        verbose_name=_("Date demandée")
    )
    completed_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Date de complétion")
    )
    tracking_number = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_("Numéro de suivi")
    )
    driver = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        limit_choices_to={'groups__name': 'Drivers'},
        verbose_name=_("Chauffeur assigné")
    )
    notes = models.TextField(
        blank=True,
        verbose_name=_("Notes internes")
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Date de création")
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Dernière mise à jour")
    )

    class Meta:
        verbose_name = _("Demande de livraison")
        verbose_name_plural = _("Demandes de livraison")
        ordering = ['-requested_date']
        permissions = [
            ("can_track_delivery", _("Peut suivre les livraisons")),
            ("can_assign_driver", _("Peut assigner un chauffeur")),
        ]

    def __str__(self):
        return f"Livraison #{self.id} - {self.reservation.voiture} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        """Mise à jour automatique de la date de complétion"""
        if self.status == 'COMPLETED' and not self.completed_date:
            from django.utils import timezone
            self.completed_date = timezone.now()
        super().save(*args, **kwargs)

    @property
    def duration(self):
        """Durée totale de la livraison en heures"""
        if self.completed_date:
            delta = self.completed_date - self.requested_date
            return round(delta.total_seconds() / 3600, 2)
        return None

    @property
    def total_cost(self):
        """Coût total incluant les options"""
        return self.delivery_option.price + (
            self.reservation.voiture.prix_chauffeur if self.driver else 0
        )
        
class DeliveryPricing(models.Model):
    option = models.ForeignKey(DeliveryOption, on_delete=models.CASCADE)
    distance_min = models.PositiveIntegerField()  # en km
    distance_max = models.PositiveIntegerField()
    base_price = models.DecimalField(max_digits=6, decimal_places=2)
    price_per_km = models.DecimalField(max_digits=6, decimal_places=2)
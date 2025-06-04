from django.utils import timezone
from decimal import Decimal
from ..models import (
    User, 
    Reservation, 
    Evaluation, 
    EvaluationLoueur,
    Litige,
    Paiement
)

class TrustService:
    @classmethod
    def calculate_user_trust_score(cls, user):
        """Calcule le score de confiance complet"""
        metrics = {
            'base_score': 70,
            'factors': {}
        }
        
        # Facteurs communs aux deux types d'utilisateurs
        metrics['factors']['account_age'] = cls._calculate_account_age_factor(user)
        metrics['factors']['completion_score'] = cls._calculate_profile_completion(user)
        
        if user.user_type == 'LOUEUR':
            metrics.update(cls._calculate_loueur_metrics(user))
            metrics['base_score'] = 50  # Score de base différent
        else:
            metrics.update(cls._calculate_proprietaire_metrics(user))
            metrics['base_score'] = 60
        
        # Calcul du score final (pondération des facteurs)
        final_score = metrics['base_score']
        for factor, value in metrics['factors'].items():
            final_score += value['impact'] * value['value']
        
        # Garder le score entre 0 et 100
        final_score = max(0, min(100, final_score))
        
        return {
            'score': round(final_score),
            'metrics': metrics
        }

    @staticmethod
    def _calculate_account_age_factor(user):
        """Ancienneté du compte (max +5 points)"""
        days = (timezone.now() - user.date_joined).days
        return {
            'value': min(5, days // 30),  # +1 point par mois, max 5
            'impact': 1,
            'description': f"Compte actif depuis {days} jours"
        }

    @staticmethod
    def _calculate_profile_completion(user):
        """Complétude du profil (max +10 points)"""
        completion = 0
        if user.photo: completion += 2
        if user.phone: completion += 2
        if user.city: completion += 2
        if user.country: completion += 2
        if user.date_naissance: completion += 2
        
        return {
            'value': completion,
            'impact': 1,
            'description': "Profil complété à {}%".format(completion * 10)
        }

    @staticmethod
    def _calculate_loueur_metrics(user):
        """Calcul spécifique aux loueurs"""
        metrics = {
            'reservation_history': {
                'value': user.reservations_client.filter(statut='termine').count(),
                'impact': 0.5,
                'description': "Nombre de locations complétées"
            },
            'cancellation_rate': {
                'value': 1 - (user.reservations_client.filter(statut='annule').count() / 
                             max(1, user.reservations_client.count())),
                'impact': 10,
                'description': "Taux d'annulation"
            },
            'average_rating': {
                'value': EvaluationLoueur.objects.filter(evalue=user)
                          .aggregate(avg=models.Avg('note'))['avg'] or 0,
                'impact': 3,
                'description': "Note moyenne reçue"
            },
            'dispute_rate': {
                'value': 1 - (Litige.objects.filter(reservation__client=user).count() / 
                             max(1, user.reservations_client.count())),
                'impact': 8,
                'description': "Taux de litiges"
            }
        }
        return {'factors': metrics}

    @staticmethod
    def _calculate_proprietaire_metrics(user):
        """Calcul spécifique aux propriétaires"""
        metrics = {
            'vehicle_quality': {
                'value': Evaluation.objects.filter(voiture__proprietaire=user)
                          .aggregate(avg=models.Avg('note'))['avg'] or 0,
                'impact': 4,
                'description': "Note moyenne des véhicules"
            },
            'response_time': {
                'value': min(5, user.reservations.filter(statut='confirme')
                          .aggregate(avg=models.Avg(F('date_modification') - F('date_creation')))['avg'].seconds // 3600 or 24),
                'impact': 2,
                'description': "Temps moyen de réponse (heures)"
            },
            'payment_reliability': {
                'value': Paiement.objects.filter(reservation__voiture__proprietaire=user, statut='REUSSI').count() / 
                        max(1, Paiement.objects.filter(reservation__voiture__proprietaire=user).count()),
                'impact': 6,
                'description': "Fiabilité des paiements"
            }
        }
        return {'factors': metrics}
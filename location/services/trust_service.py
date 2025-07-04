from django.db.models import Q
from django.db import transaction
from django.utils import timezone
from ..models import User, Reservation, Evaluation, EvaluationLoueur, Litige

class TrustService:
    """
    Service pour gérer le calcul et la mise à jour des scores de confiance des utilisateurs
    """
    
    # Configuration des scores
    BASE_SCORE = 50
    MAX_SCORE = 100
    MIN_SCORE = 0
    
    # Poids des différents facteurs
    WEIGHTS = {
        'completed_reservations': 0.3,
        'positive_ratings': 0.25,
        'negative_ratings': -0.35,
        'response_time': 0.1,
        'disputes': -0.5,
        'account_age': 0.15,
        'documents_verified': 0.4
    }

    # Seuils pour les catégories de confiance
    TRUST_CATEGORIES = {
        'excellent': 80,
        'bon': 60,
        'moyen': 40,
        'a_ameliorer': 0
    }

    @staticmethod
    def calculate_user_trust_score(user):
        """
        Calcule le score de confiance d'un utilisateur en fonction de divers critères
        
        Args:
            user (User): Instance du modèle User
        
        Returns:
            int: Score de confiance calculé (entre 0 et 100)
        
        Raises:
            ValueError: Si l'utilisateur n'est pas une instance valide
        """
        if not isinstance(user, User):
            raise ValueError("L'argument doit être une instance de User")

        # Collecte des métriques
        metrics = {
            'completed_reservations': TrustService._get_completed_reservations(user),
            'positive_ratings': TrustService._get_positive_ratings(user),
            'negative_ratings': TrustService._get_negative_ratings(user),
            'disputes': TrustService._get_disputes(user),
            'account_age': TrustService._get_account_age_score(user),
            'documents_verified': 1 if user.is_verified else 0,
            'response_time': TrustService._get_response_time_score(user)
        }

        # Calcul du score pondéré
        score = TrustService.BASE_SCORE
        for factor, weight in TrustService.WEIGHTS.items():
            score += metrics[factor] * weight * 10  # *10 pour amplifier l'impact

        # Normalisation entre MIN_SCORE et MAX_SCORE
        return max(TrustService.MIN_SCORE, min(round(score), TrustService.MAX_SCORE))

    @staticmethod
    def _get_completed_reservations(user):
        """Nombre de réservations complétées avec succès"""
        return Reservation.objects.filter(
            Q(client=user) | Q(voiture__proprietaire=user),
            statut='termine'
        ).count()

    @staticmethod
    def _get_positive_ratings(user):
        """Nombre d'évaluations positives (note >= 4)"""
        if user.user_type == 'LOUEUR':
            return EvaluationLoueur.objects.filter(evalue=user, note__gte=4).count()
        return Evaluation.objects.filter(voiture__proprietaire=user, note__gte=4).count()

    @staticmethod
    def _get_negative_ratings(user):
        """Nombre d'évaluations négatives (note <= 2)"""
        if user.user_type == 'LOUEUR':
            return EvaluationLoueur.objects.filter(evalue=user, note__lte=2).count()
        return Evaluation.objects.filter(voiture__proprietaire=user, note__lte=2).count()

    @staticmethod
    def _get_disputes(user):
        """Nombre de litiges non résolus"""
        return Litige.objects.filter(
            Q(reservation__client=user) | Q(reservation__voiture__proprietaire=user),
            statut='en_cours'
        ).count()

    @staticmethod
    def _get_account_age_score(user):
        """Score basé sur l'ancienneté du compte (en mois, max 24 mois)"""
        months = (timezone.now() - user.date_joined).days // 30
        return min(months / 2, 12)  # Normalisé sur 12 points max

    @staticmethod
    def _get_response_time_score(user):
        """
        Score basé sur le temps moyen de réponse aux messages
        (Implémentation simplifiée - à adapter selon votre logique métier)
        """
        # Exemple: 1 point par jour sous le seuil de 48h de réponse moyenne
        avg_response_hours = 24  # Remplacer par votre calcul réel
        return max(0, (48 - avg_response_hours) / 24)

    @staticmethod
    @transaction.atomic
    def update_trust_score(user):
        """
        Met à jour le score de confiance de l'utilisateur en base de données
        
        Args:
            user (User): Instance du modèle User à mettre à jour
        
        Returns:
            int: Nouveau score de confiance
        """
        new_score = TrustService.calculate_user_trust_score(user)
        
        user.trust_score = new_score
        user.last_trust_update = timezone.now()
        user.save(update_fields=['trust_score', 'last_trust_update'])
        
        return new_score

    @staticmethod
    def get_trust_category(score=None, user=None):
        """
        Retourne la catégorie de confiance sous forme de texte
        
        Args:
            score (int, optional): Score numérique. Defaults to None.
            user (User, optional): Instance User. Defaults to None.
        
        Returns:
            str: Catégorie de confiance ('excellent', 'bon', 'moyen', 'a_ameliorer')
        """
        if user is not None and score is None:
            score = user.trust_score
        
        if score is None:
            return 'non_calcule'
            
        for category, threshold in TrustService.TRUST_CATEGORIES.items():
            if score >= threshold:
                return category
        
        return 'a_ameliorer'

    @staticmethod
    def get_trust_badge(user):
        """
        Retourne les données du badge de confiance pour l'affichage
        
        Args:
            user (User): Instance du modèle User
        
        Returns:
            dict: {
                'score': int,
                'category': str,
                'last_update': datetime,
                'progress': float (0-1)
            }
        """
        return {
            'score': user.trust_score,
            'category': TrustService.get_trust_category(user=user),
            'last_update': user.last_trust_update,
            'progress': user.trust_score / 100 if user.trust_score else 0
        }


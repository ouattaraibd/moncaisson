from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import F
from location.models import LoyaltyProfile, UserReward, Reward

class LoyaltyService:
    ACTIVITY_POINTS = {
        # Activités de base
        'INSCRIPTION': 100,
        'CONNEXION_QUOTIDIENNE': 10,
        'PROFIL_COMPLET': 50,
        
        # Réservations
        'RESERVATION': 50,
        'RESERVATION_ANNULEE': -30,
        'RESERVATION_TERMINEE': 80,
        
        # Évaluations
        'EVALUATION_DONNEE': 30,
        'EVALUATION_RECUE': 20,
        
        # Transactions
        'PAIEMENT': 20,
        'RETRAIT': 15,
        
        # Social
        'PARRAINAGE': 100,
        'FILLEUL_ACTIF': 200,
        
        # Événements spéciaux
        'ANNIVERSAIRE': 200,
        'PROMOTION': 50,
        'DEFI_RELEVE': 300
    }

    @staticmethod
    def get_user_profile(user):
        """Récupère ou crée un profil de fidélité"""
        profile, created = LoyaltyProfile.objects.get_or_create(
            user=user,
            defaults={'points': 0, 'level': 'BRONZE', 'badges': [], 'special_badges': []}
        )
        return profile

    @staticmethod
    @transaction.atomic
    def add_points(user, points, activity_type=None, description=None):
        """
        Ajoute des points de fidélité avec suivi d'activité
        Args:
            user: L'utilisateur concerné
            points: Nombre de points à ajouter (peut être négatif)
            activity_type: Type d'activité (optionnel)
            description: Description détaillée (optionnel)
        """
        if points == 0:
            return 0

        profile = LoyaltyService.get_user_profile(user)
        
        # Mise à jour atomique des points
        LoyaltyProfile.objects.filter(pk=profile.pk).update(
            points=F('points') + points,
            last_updated=timezone.now()
        )
        
        # Rafraîchir l'objet
        profile.refresh_from_db()
        
        # Vérification des badges
        profile.check_badges()
        
        # Historique des activités (si nécessaire)
        if activity_type:
            LoyaltyService.record_activity(
                user=user,
                activity_type=activity_type,
                points=points,
                description=description
            )
        
        return profile.points

    @staticmethod
    def add_activity_points(user, activity_type, description=None):
        """
        Ajoute des points selon le type d'activité prédéfini
        Args:
            user: L'utilisateur concerné
            activity_type: Type d'activité (voir ACTIVITY_POINTS)
            description: Description détaillée (optionnel)
        """
        points = LoyaltyService.ACTIVITY_POINTS.get(activity_type, 0)
        
        if points == 0:
            return 0
            
        return LoyaltyService.add_points(
            user=user,
            points=points,
            activity_type=activity_type,
            description=description
        )

    @staticmethod
    def record_activity(user, activity_type, points, description=None):
        """
        Enregistre une activité dans l'historique
        (À implémenter selon votre modèle d'historique)
        """
        # Exemple d'implémentation basique :
        from location.models import LoyaltyActivityLog
        LoyaltyActivityLog.objects.create(
            user=user,
            activity_type=activity_type,
            points=points,
            description=description
        )

    @staticmethod
    def award_special_badge(user, badge_code):
        """
        Attribue un badge spécial manuellement
        Args:
            user: L'utilisateur concerné
            badge_code: Code du badge spécial
        """
        profile = LoyaltyService.get_user_profile(user)
        return profile.add_special_badge(badge_code)

    @staticmethod
    def get_user_progress(user):
        """
        Retourne la progression complète de l'utilisateur
        Returns:
            dict: {
                'points': int,
                'level': str,
                'current_badges': list,
                'next_badge': dict,
                'progress_percentage': float
            }
        """
        profile = LoyaltyService.get_user_profile(user)
        next_badge = profile.get_next_badge()
        
        return {
            'points': profile.points,
            'level': profile.get_level_display(),
            'current_badges': profile.get_current_badges(),
            'next_badge': next_badge,
            'progress_percentage': next_badge['progress'] if next_badge else 100
        }

    @staticmethod
    def redeem_reward(user, reward_id):
        """
        Échange des points contre une récompense
        Args:
            user: L'utilisateur concerné
            reward_id: ID de la récompense
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            reward = Reward.objects.get(pk=reward_id, is_active=True)
            profile = LoyaltyService.get_user_profile(user)
            
            if profile.points < reward.min_points_required:
                return False, "Points insuffisants pour cette récompense"
                
            if not reward.is_available():
                return False, "Cette récompense n'est plus disponible"
                
            # Création de la récompense utilisateur
            UserReward.objects.create(
                user=user,
                reward=reward,
                status='PENDING'
            )
            
            # Déduction des points
            LoyaltyService.add_points(
                user=user,
                points=-reward.min_points_required,
                activity_type='REDEMPTION',
                description=f"Récompense: {reward.name}"
            )
            
            return True, f"Récompense '{reward.name}' obtenue avec succès"
            
        except Reward.DoesNotExist:
            return False, "Récompense introuvable"
        except Exception as e:
            return False, f"Erreur lors de l'échange: {str(e)}"

    @staticmethod
    def get_available_rewards(user):
        """Retourne les récompenses disponibles pour l'utilisateur"""
        profile = LoyaltyService.get_user_profile(user)
        return Reward.objects.filter(
            is_active=True,
            min_points_required__lte=profile.points
        ).exclude(
            user_rewards__user=user,
            user_rewards__is_used=False
        )


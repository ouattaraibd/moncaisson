from django.views.generic import ListView, View, TemplateView
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.db.models import Count
from location.models import Reward, UserReward, LoyaltyProfile  # Maintenant importés correctement

class BadgeListView(LoginRequiredMixin, TemplateView):
    template_name = 'location/rewards/badges.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = self.request.user.loyalty_profile
        
        # Calcul des statistiques
        stats = self.get_user_stats(self.request.user)
        
        # Badges actuels (standards + spéciaux)
        current_badges = profile.get_current_badges()
        
        # Prochain badge à atteindre
        next_badge = profile.get_next_badge()
        
        # Tous les badges disponibles avec détails complets
        all_badges = profile.get_all_badges_info()
        
        # Récompenses disponibles
        available_rewards = Reward.objects.filter(
            is_active=True,
            min_points_required__lte=profile.points
        ).exclude(
            user_rewards__user=self.request.user,
            user_rewards__is_used=False
        )[:4]  # Limite à 4 récompenses pour l'affichage
        
        # Historique des points
        points_history = self.get_points_history(self.request.user)
        
        context.update({
            'profile': profile,
            'current_badges': current_badges,
            'next_badge': next_badge,
            'all_badges': all_badges,
            'stats': stats,
            'available_rewards': available_rewards,
            'points_history': points_history,
            'current_year': timezone.now().year,
            'progress_percentage': self.calculate_level_progress(profile),
            'badge_counts': {
                'total': len(all_badges),
                'earned': len(current_badges),
                'remaining': len(all_badges) - len(current_badges)
            }
        })
        return context
    
    def get_user_stats(self, user):
        """Calcule les statistiques de l'utilisateur"""
        return {
            'reservations_count': user.reservations.count(),
            'parrainage_level': user.loyalty_profile.get_parrainage_level(),
            'filleuls_count': user.filleuls.count(),
            'evaluations_count': user.evaluations_donnees.count(),
            'days_active': (timezone.now() - user.date_joined).days,
            'reward_points_earned': user.loyalty_profile.points,
            'rewards_claimed': UserReward.objects.filter(user=user).count()
        }
    
    def get_points_history(self, user, months=6):
        """Récupère l'historique des points (simplifié)"""
        from datetime import timedelta
        history = []
        now = timezone.now()
        
        for i in range(months, -1, -1):
            month = now - timedelta(days=30*i)
            history.append({
                'month': month.strftime('%b %Y'),
                'points': 100 * (months - i)  # Valeur factice - à remplacer par vos données réelles
            })
        
        return history
    
    def calculate_level_progress(self, profile):
        """Calcule la progression vers le prochain niveau"""
        if profile.level == 'BRONZE':
            return min(100, profile.points / 500 * 100)
        elif profile.level == 'SILVER':
            return min(100, (profile.points - 500) / 1500 * 100)
        elif profile.level == 'GOLD':
            return 100
        return 0


class RewardListView(LoginRequiredMixin, TemplateView):
    template_name = 'location/rewards/list.html'
    paginate_by = 10
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = self.request.user.loyalty_profile
        
        rewards = Reward.objects.filter(
            is_active=True,
            min_points_required__lte=profile.points
        ).annotate(
            claimed_count=Count('user_rewards')
        ).order_by('min_points_required')
        
        # Exclure les récompenses déjà réclamées et non utilisées
        rewards = rewards.exclude(
            user_rewards__user=self.request.user,
            user_rewards__is_used=False
        )
        
        context.update({
            'rewards': rewards,
            'user_points': profile.points,
            'can_claim_any': any(r.min_points_required <= profile.points for r in rewards)
        })
        return context
        
class ClaimRewardView(LoginRequiredMixin, View):
    def post(self, request, reward_id):
        profile = request.user.loyalty_profile
        try:
            reward = Reward.objects.get(pk=reward_id, is_active=True)
            
            if profile.points < reward.min_points_required:
                messages.error(request, "Points insuffisants pour cette récompense")
                return redirect('rewards_list')
                
            # Vérifier si la récompense n'a pas déjà été réclamée
            if UserReward.objects.filter(user=request.user, reward=reward, is_used=False).exists():
                messages.warning(request, "Vous avez déjà cette récompense")
                return redirect('rewards_list')
                
            # Créer la récompense utilisateur
            UserReward.objects.create(
                user=request.user,
                reward=reward,
                status='PENDING'
            )
            
            # Déduire les points
            profile.points -= reward.min_points_required
            profile.save()
            
            messages.success(request, f"Récompense '{reward.name}' obtenue avec succès!")
            return redirect('rewards_list')
            
        except Reward.DoesNotExist:
            messages.error(request, "Récompense introuvable")
            return redirect('rewards_list')


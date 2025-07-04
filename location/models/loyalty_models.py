from django.db import models
from location.models.core_models import User

class Reward(models.Model):
    REWARD_TYPES = [
        ('DISCOUNT', 'Code de réduction'),
        ('CASHBACK', 'Cashback'), 
        ('GIFT', 'Cadeau'),
        ('LOYALTY', 'Points de fidélité')
    ]
    
    name = models.CharField(
        max_length=100,
        verbose_name="Nom de la récompense"
    )
    reward_type = models.CharField(
        max_length=20,
        choices=REWARD_TYPES,
        default='LOYALTY',  # Valeur par défaut ajoutée
        verbose_name="Type de récompense"
    )
    value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,  # Ajoutez cette ligne
        verbose_name="Valeur"
    )
    description = models.TextField(
        verbose_name="Description"
    )
    image = models.ImageField(
        upload_to='rewards/',
        null=True,
        blank=True,
        verbose_name="Image"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Active"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création"
    )
    expiry_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Date d'expiration"
    )
    min_points_required = models.PositiveIntegerField(
        default=0,
        verbose_name="Points minimum requis"
    )
    stock_quantity = models.PositiveIntegerField(
        default=1,
        verbose_name="Quantité disponible"
    )

    class Meta:
        verbose_name = "Récompense"
        verbose_name_plural = "Récompenses"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['reward_type']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_reward_type_display()})"

    def is_available(self):
        """Vérifie si la récompense est disponible"""
        from django.utils import timezone
        if not self.is_active:
            return False
        if self.expiry_date and self.expiry_date < timezone.now().date():
            return False
        if self.stock_quantity <= 0:
            return False
        return True

    def claim(self, user):
        """Méthode pour attribuer la récompense à un utilisateur"""
        from . import UserReward
        if not self.is_available():
            raise ValueError("Cette récompense n'est plus disponible")
        return UserReward.objects.create(
            user=user,
            reward=self,
            status='PENDING'
        )

class UserReward(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='user_rewards'  # Modifié pour éviter les conflits
    )
    reward = models.ForeignKey(
        Reward,
        on_delete=models.CASCADE,
        related_name='user_rewards'
    )
    claimed_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)
    code = models.CharField(max_length=50, unique=True, blank=True)

    class Meta:
        verbose_name = "Récompense utilisateur"
        verbose_name_plural = "Récompenses utilisateurs"
        unique_together = ('user', 'reward')
        ordering = ['-claimed_at']

    def __str__(self):
        return f"{self.user.username} - {self.reward.name}"
        
class LoyaltyProfile(models.Model):
    LEVEL_CHOICES = [
        ('BRONZE', 'Bronze (0-499 points)'),
        ('SILVER', 'Argent (500-1999 points)'), 
        ('GOLD', 'Or (2000+ points)')
    ]
    
    BADGE_TIERS = {
        'NOUVEAU': {'min': 0, 'max': 49, 'color': '#cd7f32', 'icon': 'fa-star'},
        'BRONZE': {'min': 50, 'max': 199, 'color': '#cd7f32', 'icon': 'fa-shield-alt'},
        'SILVER': {'min': 200, 'max': 499, 'color': '#c0c0c0', 'icon': 'fa-award'},
        'GOLD': {'min': 500, 'max': 999, 'color': '#ffd700', 'icon': 'fa-trophy'},
        'PLATINUM': {'min': 1000, 'max': 1999, 'color': '#e5e4e2', 'icon': 'fa-crown'},
        'DIAMOND': {'min': 2000, 'max': float('inf'), 'color': '#b9f2ff', 'icon': 'fa-gem'},
        'VIP': {'min': 5000, 'max': float('inf'), 'color': '#ff00ff', 'icon': 'fa-star'}
    }

    SPECIAL_BADGES = {
        'PARRAIN_1': {'condition': lambda p: p.get_parrainage_level() >= 1, 'color': '#4CAF50', 'icon': 'fa-user-plus'},
        'PARRAIN_2': {'condition': lambda p: p.get_parrainage_level() >= 2, 'color': '#2196F3', 'icon': 'fa-users'},
        'PARRAIN_3': {'condition': lambda p: p.get_parrainage_level() >= 3, 'color': '#9C27B0', 'icon': 'fa-people-arrows'}
    }

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='loyalty_profile'
    )
    points = models.PositiveIntegerField(default=0)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='BRONZE')
    last_updated = models.DateTimeField(auto_now=True)
    badges = models.JSONField(default=list)
    special_badges = models.JSONField(default=list)

    class Meta:
        verbose_name = "Profil de fidélité"
        verbose_name_plural = "Profils de fidélité"
        ordering = ['-points']

    def __str__(self):
        return f"{self.user.username} - {self.get_level_display()} ({self.points} pts)"

    def update_level(self):
        """Met à jour le niveau de fidélité en fonction des points"""
        if self.points >= 2000:
            self.level = 'GOLD'
        elif self.points >= 500:
            self.level = 'SILVER'
        else:
            self.level = 'BRONZE'
        self.save()
        return self.level

    def add_points(self, points):
        """Ajoute des points et met à jour le niveau"""
        self.points += points
        self.save()
        self.update_level()
        self.check_badges()
        return self.points

    def check_badges(self):
        """Vérifie et attribue les badges automatiquement"""
        # Badges basés sur les points
        for badge_code, tier in self.BADGE_TIERS.items():
            if tier['min'] <= self.points <= tier['max'] and badge_code not in self.badges:
                self.add_badge(badge_code)

        # Badges spéciaux
        for badge_code, config in self.SPECIAL_BADGES.items():
            if config['condition'](self) and badge_code not in self.special_badges:
                self.add_special_badge(badge_code)

    def add_badge(self, badge_code):
        """Ajoute un badge standard"""
        if badge_code not in self.badges:
            self.badges.append(badge_code)
            self.save()
            return True
        return False

    def add_special_badge(self, badge_code):
        """Ajoute un badge spécial"""
        if badge_code not in self.special_badges:
            self.special_badges.append(badge_code)
            self.save()
            return True
        return False

    def get_current_badges(self):
        """Retourne les badges mérités par l'utilisateur avec leurs détails"""
        earned_badges = []
        
        # Badges standards
        for badge_code in self.badges:
            if badge_code in self.BADGE_TIERS:
                tier = self.BADGE_TIERS[badge_code]
                earned_badges.append({
                    'code': badge_code,
                    'name': badge_code.capitalize(),
                    'color': tier['color'],
                    'icon': tier['icon'],
                    'type': 'standard',
                    'progress': min(100, (self.points - tier['min']) / (tier['max'] - tier['min']) * 100) 
                            if tier['max'] != float('inf') else 100
                })
        
        # Badges spéciaux
        for badge_code in self.special_badges:
            if badge_code in self.SPECIAL_BADGES:
                config = self.SPECIAL_BADGES[badge_code]
                earned_badges.append({
                    'code': badge_code,
                    'name': badge_code.replace('_', ' ').capitalize(),
                    'color': config['color'],
                    'icon': config['icon'],
                    'type': 'special',
                    'progress': 100
                })
        
        return earned_badges

    def get_next_badge(self):
        """Retourne le prochain badge à atteindre"""
        for badge_code, tier in sorted(self.BADGE_TIERS.items(), key=lambda x: x[1]['min']):
            if self.points < tier['min']:
                return {
                    'code': badge_code,
                    'name': badge_code.capitalize(),
                    'points_needed': tier['min'] - self.points,
                    'progress': min(100, self.points / tier['min'] * 100),
                    'color': tier['color'],
                    'icon': tier['icon']
                }
        return None

    def get_parrainage_level(self):
        """Retourne le niveau de parrainage"""
        filleuls = self.user.filleuls.count()
        if filleuls >= 10: return 3
        elif filleuls >= 5: return 2
        elif filleuls >= 1: return 1
        return 0

    def get_all_badges_info(self):
        """Retourne tous les badges disponibles avec état de déblocage"""
        all_badges = []
        
        # Badges standards
        for badge_code, tier in self.BADGE_TIERS.items():
            all_badges.append({
                'code': badge_code,
                'name': badge_code.capitalize(),
                'min_points': tier['min'],
                'description': f"Atteignez {tier['min']} points",
                'color': tier['color'],
                'icon': tier['icon'],
                'earned': badge_code in self.badges,
                'type': 'standard'
            })
        
        # Badges spéciaux
        for badge_code, config in self.SPECIAL_BADGES.items():
            all_badges.append({
                'code': badge_code,
                'name': badge_code.replace('_', ' ').capitalize(),
                'description': self.get_special_badge_description(badge_code),
                'color': config['color'],
                'icon': config['icon'],
                'earned': badge_code in self.special_badges,
                'type': 'special'
            })
        
        return all_badges

    def get_special_badge_description(self, badge_code):
        """Retourne la description d'un badge spécial"""
        descriptions = {
            'PARRAIN_1': "Parrainez au moins 1 membre",
            'PARRAIN_2': "Parrainez au moins 5 membres",
            'PARRAIN_3': "Parrainez au moins 10 membres"
        }
        return descriptions.get(badge_code, "Badge spécial")
        
class MessageReward(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    points_earned = models.PositiveIntegerField(default=5)
    reason = models.CharField(max_length=100)  # "Premier message", etc.


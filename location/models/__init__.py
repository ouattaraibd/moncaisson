# Supprimez les doublons dans les imports
from .core_models import (
    User,
    Voiture,
    Reservation,
    DocumentVerification,
    Evaluation,
    EvaluationLoueur,
    Portefeuille,
    Transaction,
    ProprietaireProfile, 
    LoueurProfile,
    Paiement,
    Favoris,
    PageView,
    DrivingHistory,
    Litige
)

from .loyalty_models import Reward, UserReward, LoyaltyProfile  # Import unique depuis loyalty_models
from .delivery_models import DeliveryOption, DeliveryRequest
from .policy_models import Policy, PolicyAcceptance
from .messaging_models import Message, Conversation, MessageAttachment, ConversationArchive

__all__ = [
    'User',
    'Voiture',
    'Reservation',
    'DocumentVerification',
    'Evaluation',
    'EvaluationLoueur', 
    'Portefeuille',
    'Transaction',
    'ProprietaireProfile',
    'LoueurProfile',
    'Paiement',
    'Favoris',
    'Reward',  # Uniquement depuis loyalty_models
    'UserReward',  # Uniquement depuis loyalty_models
    'DeliveryOption',
    'DeliveryRequest',
    'Policy',
    'Litige',
    'PolicyAcceptance',
    'PageView',
    'DrivingHistory',
    'Message',
    'Conversation', 
    'MessageAttachment',
    'ConversationArchive'
]
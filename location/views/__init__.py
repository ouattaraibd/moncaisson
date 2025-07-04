from .auth_views import *
from .voiture_views import ajouter_favoris, retirer_favoris, liste_favoris, ListeVoitures, VoitureDetail, ajouter_voiture, ModifierVoiture, RechercheVoitures
from .reservation_views import *
from .dashboard_views import *
from .payment_views import initier_paiement, confirmation_paiement
from .verification_views import *
from .evaluation_views import *
#from .admin_dashboard import super_dashboard, validate_content#

# Rate limit settings
DEFAULT_RATE_LIMITS = {
    'auth': '5/m',
    'payments': '3/m', 
    'api': '10/m'
}  
    


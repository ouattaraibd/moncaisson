from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth.views import LogoutView
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from location import routing as location_routing
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView
)

# Configuration ASGI pour Channels
application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": URLRouter(location_routing.websocket_urlpatterns)
})

# Configuration des URLs de base
urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    path('admin/logout/', LogoutView.as_view(next_page='/admin/login/')),
    
    # Authentification
    path('accounts/', include('django.contrib.auth.urls')),
    
    # Application principale
    path('', include('location.urls')),
    
    #Honeypot
    path('', include('honeypot.urls')),  # URLs pièges
    
    # Authentification JWT (globale)
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    
    # API
    path('api/v1/', include(('api.urls', 'api'), namespace='api-v1')),
    
    # WebSocket
    path('ws/', include(location_routing.websocket_urlpatterns)),
    
    # Chatbot                                           
    path('chat/', include('location.urls_chatbot')),
]

# Configuration spécifique au mode DEBUG
if settings.DEBUG:
    # Servir les fichiers média et statiques
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    
    # Debug Toolbar (uniquement si installé)
    if settings.DEBUG:
        try:
            import debug_toolbar
            urlpatterns += [
                path('__debug__/', include(debug_toolbar.urls)),
            ]
        except ImportError:
            pass  # Debug Toolbar n'est pas installé, on ignore silencieusement
        
handler429 = 'location.views.error_handlers.handle_ratelimit_error'

# En production, assurez-vous que votre serveur web (Nginx/Apache) est configuré pour servir:
# - Les fichiers statiques (settings.STATIC_URL -> settings.STATIC_ROOT)
# - Les fichiers média (settings.MEDIA_URL -> settings.MEDIA_ROOT)


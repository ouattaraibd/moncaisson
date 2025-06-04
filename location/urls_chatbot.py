from django.urls import path
from location.views.chatbot_views import chat_interface, chat_api

urlpatterns = [
    path('chat/', chat_interface, name='chat_interface'),
    path('api/chat/', chat_api, name='chat_api'),  # Optionnel pour AJAX
]
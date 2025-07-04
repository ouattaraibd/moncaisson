from django.urls import re_path
from location.consumers import ChatbotConsumer 

websocket_urlpatterns = [
    re_path(r'ws/chatbot/$', ChatbotConsumer.as_asgi()),
]


import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user_id = self.scope['url_route']['kwargs']['user_id']
        self.room_group_name = f'notifs_{self.user_id}'
        
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'send_notification',
                'message': data['message']
            }
        )

    async def send_notification(self, event):
        await self.send(text_data=json.dumps({
            'message': event['message']
        }))
        
class ChatbotConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        await self.send_welcome_message()

    async def disconnect(self, close_code):
        pass

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            user_message = data.get('message', '').strip().lower()
            
            # Typing indicator
            await self.send(json.dumps({'action': 'typing'}))
            
            # Simple response logic
            if any(greeting in user_message for greeting in ['bonjour', 'salut', 'hello']):
                response = "Bonjour ! Comment puis-je vous aider pour votre location de voiture ?"
            elif 'disponible' in user_message:
                response = await self.get_available_cars()
            elif 'tarif' in user_message or 'prix' in user_message:
                response = "Nos tarifs commencent à 15 000 XOF/jour. Quelle marque vous intéresse ?"
            elif 'réserver' in user_message or 'reserver' in user_message:
                response = "Vous pouvez réserver directement sur notre site. Souhaitez-vous que je vous guide ?"
            elif 'contact' in user_message or 'contacter' in user_message:
                response = "Vous pouvez nous contacter au +225 XX XX XX XX ou par email à contact@moncaisson.com"
            elif 'heure' in user_message or 'ouvert' in user_message:
                response = "Nous sommes ouverts du lundi au samedi de 8h à 19h."
            elif 'merci' in user_message or 'remercie' in user_message:
                response = "Je vous en prie ! N'hésitez pas si vous avez d'autres questions."
            elif 'au revoir' in user_message or 'bye' in user_message:
                response = "Au revoir et à bientôt pour votre location de voiture !"
            else:
                response = "Je peux vous aider avec :\n- Les disponibilités\n- Les tarifs\n- Les réservations\n- Nos coordonnées\n\nQue souhaitez-vous savoir ?"
            
            await self.send(json.dumps({
                'message': response,
                'action': 'response'
            }))

        except Exception as e:
            logger.error(f"Erreur chatbot: {str(e)}")
            await self.send(json.dumps({
                'message': "Désolé, une erreur est survenue. Veuillez réessayer.",
                'action': 'error'
            }))

    async def send_welcome_message(self):
        welcome_msg = (
            "Bonjour ! Je suis l'assistant de location de voitures. "
            "Posez-moi vos questions sur :\n"
            "- Les voitures disponibles\n"
            "- Les tarifs\n"
            "- Le processus de réservation\n"
            "- Nos heures d'ouverture\n"
            "- Nous contacter"
        )
        await self.send(json.dumps({
            'message': welcome_msg,
            'action': 'welcome'
        }))

    @sync_to_async
    def get_available_cars(self):
        """Simule un appel à la base de données"""
        # Ici vous pourriez faire un vrai appel à votre modèle Voiture
        # Par exemple: Voiture.objects.filter(disponible=True)
        return "Nous avons actuellement 3 voitures disponibles :\n- Peugeot 208\n- Toyota Yaris\n- Renault Clio"
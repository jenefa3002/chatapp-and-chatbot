import json
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from django.contrib.auth.models import User
import logging
from .models import PrivateMessage, UserStatus

logger = logging.getLogger(__name__)

class PrivateChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        logger.info(f"Attempting WebSocket connection: {self.channel_name}")
        try:
            self.sender_username = self.scope['url_route']['kwargs']['sender_username']
            self.recipient_username = self.scope['url_route']['kwargs']['recipient_username']
            self.room_name = f"chat_{min(self.sender_username, self.recipient_username)}_{max(self.sender_username, self.recipient_username)}"
            self.room_group_name = f"chat_{self.room_name}"
            await self.channel_layer.group_add(self.room_group_name, self.channel_name)
            await self.accept()
            logger.info(f"WebSocket connected to room: {self.room_group_name}")
            logger.info(f"Connected to channel : {self.channel_name}")
        except Exception as e:
            logger.error(f"WebSocket connection error: {str(e)}")
            await self.close()

    async def disconnect(self, close_code):
        logger.info(f"WebSocket disconnected: {self.channel_name}")
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            message = text_data_json.get('message', None)
            file_url = text_data_json.get('file_url')

            if not message and not file_url:
                await self.send(text_data=json.dumps({'error': 'No message provided'}))
                return

            if message is None:
                await self.send(text_data=json.dumps({'error': 'No message provided'}))
                return

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': message,
                    'file_url': file_url,
                    'sender': self.sender_username,
                    'recipient': self.recipient_username,
                }
            )

            await self.save_message(self.sender_username, self.recipient_username, message, file_url)
            logger.info(f"Message received: {message}")
        except json.JSONDecodeError:
            logger.error("Invalid JSON received")
            await self.send(text_data=json.dumps({'error': 'Invalid JSON'}))

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))

    @sync_to_async
    def save_message(self, sender_username, recipient_username, content, file_url):
        sender_user = User.objects.get(username=sender_username)
        recipient_user = User.objects.get(username=recipient_username)
        message = PrivateMessage.objects.create(
            sender=sender_user,
            recipient=recipient_user,
            content=content,
            file=file_url
        )
        return message

    async def user_online(self, event):
        await self.send(text_data=json.dumps({
            'type': 'user_status',
            'username': event['username'],
            'status': 'online',
        }))

    async def user_offline(self, event):
        await self.send(text_data=json.dumps({
            'type': 'user_status',
            'username': event['username'],
            'status': 'offline',
        }))


    async def send_notification(self, recipient_username, message):
        recipient = await sync_to_async(User.objects.get)(username=recipient_username)
        if recipient.is_authenticated:
            await self.channel_layer.group_send(
                f"notifications_{recipient_username}",
                {
                    'type': 'notification_message',
                    'message': message,
                    'sender': self.sender_username
                }
            )

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.username = self.scope['user'].username
        self.group_name = f"notifications_{self.username}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def notification_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'sender': event['sender'],
            'message': event['message']
        }))

class ScreenShareConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_group_name = 'screenshare'
        logger.info("Attempting WebSocket connection")

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name,
        )
        await self.accept()
        logger.info("Websocket connected")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        logger.info("Websocket disconnected for Screen Shareing")

    async def receive(self, text_data):
        message = json.loads(text_data)
        logger.info("Reciving signal..")
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'signal_message',
                'message': message
            }
        )

    async def signal_message(self, event):
        message = event['message']
        await self.send(text_data=json.dumps(message))


class OnlineStatusConsumer(AsyncWebsocketConsumer):

    async def connect(self):

        self.user = self.scope["user"]
        if self.user.is_authenticated:
            await self.set_online_status(self.user, True)
            await self.channel_layer.group_add("online_users", self.channel_name)
            await self.accept()
            await self.broadcast_user_status(self.user, True)

    async def disconnect(self, close_code):
        if self.user.is_authenticated:
            await self.set_online_status(self.user, False)
            await self.channel_layer.group_discard("online_users", self.channel_name)
            await self.broadcast_user_status(self.user, False)

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data.get("message", "")
        await self.send(text_data=json.dumps({"message": message}))

    async def broadcast_user_status(self, user, is_online):
        await self.channel_layer.group_send(
            "online_users",
            {
                "type": "user_status",
                "user_id": user.id,
                "username": user.username,
                "is_online": is_online,
            }
        )

    async def user_status(self, event):
        await self.send(text_data=json.dumps(event))

    @sync_to_async
    def set_online_status(self, user, status):
        user_status, _ = UserStatus.objects.get_or_create(user=user)
        user_status.is_online = status
        user_status.save()
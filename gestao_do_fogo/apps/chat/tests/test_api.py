from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from apps.chat.models import Chat, ChatMessage, MessageTypes
from apps.users.models import CustomUser


class NewChatMessageAPITest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create(username="alice@example.com")
        self.user.set_password("123")
        self.user.save()
        self.chat = Chat.objects.create(user=self.user, name="Test Chat")
        self.client.login(username=self.user.username, password="123")

    @patch("apps.chat.views.get_chat_response.delay")
    @patch("apps.chat.views.set_chat_name.delay")
    def test_new_message(self, mock_set_name, mock_get_response):
        mock_get_response.return_value.task_id = "fake-task-id"
        response = self.client.post(
            reverse("chat:api_new_chat_message", args=[self.chat.id]),
            data={"chat": self.chat.id, "content": "Hello world"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.chat.messages.count(), 1)
        message = self.chat.messages.first()
        self.assertEqual(message.content, "Hello world")
        self.assertEqual(message.message_type, MessageTypes.HUMAN)

    @patch("apps.chat.views.get_chat_response.delay")
    @patch("apps.chat.views.set_chat_name.delay")
    def test_client_cannot_inject_system_message_type(self, mock_set_name, mock_get_response):
        mock_get_response.return_value.task_id = "fake-task-id"
        response = self.client.post(
            reverse("chat:api_new_chat_message", args=[self.chat.id]),
            data={
                "chat": self.chat.id,
                "content": "malicious",
                "message_type": MessageTypes.SYSTEM,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        message = ChatMessage.objects.get(chat=self.chat)
        self.assertEqual(message.message_type, MessageTypes.HUMAN)

    def test_nonexistent_chat_returns_404(self):
        response = self.client.post(
            reverse("chat:api_new_chat_message", args=[99999]),
            data={"chat": 99999, "content": "Hello"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)

    def test_other_users_chat_returns_404(self):
        other_user = CustomUser.objects.create(username="bob@example.com")
        other_chat = Chat.objects.create(user=other_user, name="Bob's Chat")
        response = self.client.post(
            reverse("chat:api_new_chat_message", args=[other_chat.id]),
            data={"chat": other_chat.id, "content": "Hello"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(other_chat.messages.count(), 0)

    def test_body_chat_id_mismatch_is_rejected(self):
        other_chat = Chat.objects.create(user=self.user, name="Other Chat")
        response = self.client.post(
            reverse("chat:api_new_chat_message", args=[self.chat.id]),
            data={"chat": other_chat.id, "content": "Hello"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.chat.messages.count(), 0)
        self.assertEqual(other_chat.messages.count(), 0)

    def test_unauthenticated_is_rejected(self):
        self.client.logout()
        response = self.client.post(
            reverse("chat:api_new_chat_message", args=[self.chat.id]),
            data={"chat": self.chat.id, "content": "Hello"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.chat.messages.count(), 0)

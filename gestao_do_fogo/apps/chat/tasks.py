from typing import Any

from asgiref.sync import async_to_sync
from celery import shared_task
from django.conf import settings
from pydantic_ai import Agent

from apps.chat.models import Chat, MessageTypes
from apps.chat.prompts import get_chat_naming_prompt
from apps.chat.serializers import ChatMessageSerializer
from apps.chat.sessions import ChatSession


@shared_task(bind=True)
def get_chat_response(self, chat_id: int) -> dict[str, Any]:
    chat = Chat.objects.get(id=chat_id)
    session = ChatSession.from_chat(chat)

    response = async_to_sync(session.get_response)()
    message_object = async_to_sync(session.save_message)(response, MessageTypes.AI)
    return ChatMessageSerializer(message_object).data


@shared_task
def set_chat_name(chat_id: int, message: str) -> None:
    chat = Chat.objects.filter(id=chat_id).first()
    if not chat or not message:
        return
    if len(message) < 30:
        # for short messages, just use them as the chat name. the summary won't help
        chat.name = message
        chat.save()
    else:
        agent = Agent(
            settings.DEFAULT_AI_MODEL,
            instructions=get_chat_naming_prompt(),
        )
        result = agent.run_sync(f"Summarize the following text: '{message}'")
        chat.name = result.output[:100].strip()
        chat.save()

"""Channel URL routing configuration."""

from apps.group_chat.routing import websocket_urlpatterns as group_chat_patterns

urlpatterns: list = [] + group_chat_patterns

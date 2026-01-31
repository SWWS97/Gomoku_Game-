from django.urls import re_path

from .consumers import GameConsumer, LobbyConsumer  # utils 안의 consumers.py
from .direct_message_consumer import DirectMessageConsumer
from .matchmaking_consumer import MatchmakingConsumer
from .notification_consumer import NotificationConsumer

websocket_urlpatterns = [
    re_path(r"ws/games/(?P<game_id>\d+)/$", GameConsumer.as_asgi()),
    re_path(r"ws/lobby/$", LobbyConsumer.as_asgi()),
    re_path(r"ws/matchmaking/$", MatchmakingConsumer.as_asgi()),
    re_path(r"ws/dm/(?P<friend_id>\d+)/$", DirectMessageConsumer.as_asgi()),
    re_path(r"ws/notifications/$", NotificationConsumer.as_asgi()),
]

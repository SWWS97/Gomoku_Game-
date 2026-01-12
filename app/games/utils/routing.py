from django.urls import re_path

from .consumers import GameConsumer, LobbyConsumer  # utils 안의 consumers.py
from .direct_message_consumer import DirectMessageConsumer

websocket_urlpatterns = [
    re_path(r"ws/games/(?P<game_id>\d+)/$", GameConsumer.as_asgi()),
    re_path(r"ws/lobby/$", LobbyConsumer.as_asgi()),
    re_path(r"ws/dm/(?P<friend_id>\d+)/$", DirectMessageConsumer.as_asgi()),
]

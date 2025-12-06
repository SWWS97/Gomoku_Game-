from django.urls import re_path

from .consumers import GameConsumer, LobbyConsumer  # utils 안의 consumers.py

websocket_urlpatterns = [
    re_path(r"ws/games/(?P<game_id>\d+)/$", GameConsumer.as_asgi()),
    re_path(r"ws/lobby/$", LobbyConsumer.as_asgi()),
]

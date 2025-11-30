from django.urls import path

from . import views

app_name = "games"

urlpatterns = [
    path("", views.lobby, name="lobby"),  # 로비
    path("new/", views.new_game, name="new"),  # 새 방 만들기
    path("<int:pk>/join/", views.join_game, name="join"),  # 방 참가
    path("<int:pk>/", views.game_room, name="room"),  # 게임 방
]

from django.urls import path

from . import views

app_name = "games"

urlpatterns = [
    path("", views.lobby, name="lobby"),  # 로비
    path("new/", views.new_game, name="new"),  # 새 방 만들기
    path("history/", views.game_history, name="history"),  # 전적 조회
    path("<int:pk>/join/", views.join_game, name="join"),  # 방 참가
    path("<int:pk>/leave/", views.leave_game, name="leave"),  # 방 나가기
    path("<int:pk>/", views.game_room, name="room"),  # 게임 방
]

from django.urls import path
from . import views

app_name = "games"

urlpatterns = [
    path("new/", views.new_game, name="new"),
    path("<int:pk>/", views.game_room, name="room"),
]
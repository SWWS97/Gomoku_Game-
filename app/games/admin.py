from django.contrib import admin

from .models import Game, Move


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", "black", "white", "turn", "winner")


@admin.register(Move)
class MoveAdmin(admin.ModelAdmin):
    list_display = ("id", "game", "order", "x", "y", "player", "created_at")

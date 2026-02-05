from django.contrib import admin

from .models import Game, Move, Report, Sanction


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", "black", "white", "turn", "winner")


@admin.register(Move)
class MoveAdmin(admin.ModelAdmin):
    list_display = ("id", "game", "order", "x", "y", "player", "created_at")


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "reporter",
        "reported_user",
        "report_type",
        "reason",
        "status",
        "created_at",
    )
    list_filter = ("status", "report_type", "reason")


@admin.register(Sanction)
class SanctionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "sanction_type",
        "reason",
        "starts_at",
        "ends_at",
        "issued_by",
    )
    list_filter = ("sanction_type",)

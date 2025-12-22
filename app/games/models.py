from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()

BOARD_SIZE = 15


class Game(models.Model):
    title = models.CharField(max_length=100, default="오목 게임", help_text="방 제목")
    created_at = models.DateTimeField(auto_now_add=True)
    black = models.ForeignKey(
        User, related_name="games_as_black", null=True, on_delete=models.SET_NULL
    )
    white = models.ForeignKey(
        User, related_name="games_as_white", null=True, on_delete=models.SET_NULL
    )
    turn = models.CharField(max_length=5, default="black")  # black | white
    winner = models.CharField(
        max_length=5, null=True, blank=True
    )  # black | white | draw
    # Compact board: 15x15을 문자열로 보관: '.', 'B', 'W'
    board = models.CharField(
        max_length=BOARD_SIZE * BOARD_SIZE, default="." * (BOARD_SIZE * BOARD_SIZE)
    )
    # Timer fields: 각 플레이어당 15분 (900초)
    black_time_remaining = models.IntegerField(
        default=900, help_text="흑 플레이어 남은 시간 (초)"
    )
    white_time_remaining = models.IntegerField(
        default=900, help_text="백 플레이어 남은 시간 (초)"
    )
    last_move_time = models.DateTimeField(
        null=True, blank=True, help_text="마지막 착수 시간"
    )
    # Ready system fields
    black_ready = models.BooleanField(default=False, help_text="흑 플레이어 준비 완료")
    white_ready = models.BooleanField(default=False, help_text="백 플레이어 준비 완료")
    game_started = models.BooleanField(default=False, help_text="게임 시작 여부")
    # Rematch fields
    rematch_black = models.BooleanField(
        default=False, help_text="흑 플레이어 리매치 요청"
    )
    rematch_white = models.BooleanField(
        default=False, help_text="백 플레이어 리매치 요청"
    )

    def idx(self, x, y):
        return y * BOARD_SIZE + x

    def get_cell(self, x, y):
        return self.board[self.idx(x, y)]

    def set_cell(self, x, y, val):
        s = list(self.board)
        s[self.idx(x, y)] = val
        self.board = "".join(s)

    def stone_of_turn(self):
        return "B" if self.turn == "black" else "W"

    def swap_turn(self):
        self.turn = "white" if self.turn == "black" else "black"


class Move(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="moves")
    player = models.ForeignKey(User, on_delete=models.CASCADE)
    x = models.PositiveIntegerField()
    y = models.PositiveIntegerField()
    order = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("game", "x", "y")]
        ordering = ["order"]


class GameHistory(models.Model):
    """종료된 게임의 전적 기록"""

    game_id = models.IntegerField(help_text="원본 Game ID (삭제된 게임 참조용)")
    black = models.ForeignKey(
        User,
        related_name="history_as_black",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    white = models.ForeignKey(
        User,
        related_name="history_as_white",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    winner = models.CharField(max_length=5)  # black | white | draw
    created_at = models.DateTimeField(help_text="게임 시작 시간")
    finished_at = models.DateTimeField(auto_now_add=True, help_text="게임 종료 시간")
    total_moves = models.IntegerField(help_text="총 수 개수")

    class Meta:
        ordering = ["-finished_at"]
        indexes = [
            models.Index(fields=["black", "-finished_at"]),
            models.Index(fields=["white", "-finished_at"]),
        ]

    def __str__(self):
        return f"Game #{self.game_id} - {self.winner} won"

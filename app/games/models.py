from django.db import models

from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

BOARD_SIZE = 15

class Game(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    black = models.ForeignKey(User, related_name="games_as_black", null=True, on_delete=models.SET_NULL)
    white = models.ForeignKey(User, related_name="games_as_white", null=True, on_delete=models.SET_NULL)
    turn = models.CharField(max_length=5, default="black")  # black | white
    winner = models.CharField(max_length=5, null=True, blank=True)  # black | white | draw
    # Compact board: 15x15을 문자열로 보관: '.', 'B', 'W'
    board = models.CharField(max_length=BOARD_SIZE*BOARD_SIZE, default="."*(BOARD_SIZE*BOARD_SIZE))

    def idx(self, x, y):
        return y * BOARD_SIZE + x

    def get_cell(self, x, y):
        return self.board[self.idx(x,y)]

    def set_cell(self, x, y, val):
        s = list(self.board)
        s[self.idx(x,y)] = val
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

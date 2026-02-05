from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()

BOARD_SIZE = 15


class Game(models.Model):
    title = models.CharField(max_length=100, default="오목 게임", help_text="방 제목")
    password = models.CharField(
        max_length=128, null=True, blank=True, help_text="방 비밀번호 (선택사항)"
    )
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

    def get_player_name(self, color):
        """색상에 해당하는 플레이어의 표시 이름 반환"""
        player = self.black if color == "black" else self.white
        return (player.first_name or player.username) if player else None

    def get_both_player_names(self):
        """양쪽 플레이어의 이름을 딕셔너리로 반환"""
        return {
            "black_player": self.get_player_name("black"),
            "white_player": self.get_player_name("white"),
            "black_username": self.black.username if self.black else None,
            "white_username": self.white.username if self.white else None,
        }

    def reset_for_new_round(self):
        """새 라운드를 위해 게임판, 타이머, 턴을 초기화"""
        self.board = "." * (BOARD_SIZE * BOARD_SIZE)
        self.turn = "black"
        self.winner = None  # 승자 리셋
        self.black_time_remaining = 900
        self.white_time_remaining = 900
        self.last_move_time = None

    def clear_moves(self):
        """게임의 모든 수를 삭제"""
        self.moves.all().delete()


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


class Friend(models.Model):
    """친구 관계 모델 (양방향)"""

    user = models.ForeignKey(
        User, related_name="friends", on_delete=models.CASCADE, help_text="사용자"
    )
    friend = models.ForeignKey(
        User,
        related_name="befriended_by",
        on_delete=models.CASCADE,
        help_text="친구",
    )
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="친구 관계 생성 시간"
    )

    class Meta:
        unique_together = ["user", "friend"]
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.user.username} -> {self.friend.username}"


class FriendRequest(models.Model):
    """친구 요청 모델"""

    from_user = models.ForeignKey(
        User,
        related_name="sent_friend_requests",
        on_delete=models.CASCADE,
        help_text="요청 보낸 사용자",
    )
    to_user = models.ForeignKey(
        User,
        related_name="received_friend_requests",
        on_delete=models.CASCADE,
        help_text="요청 받은 사용자",
    )
    created_at = models.DateTimeField(auto_now_add=True, help_text="요청 생성 시간")

    class Meta:
        unique_together = ["from_user", "to_user"]
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["to_user", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.from_user.username} -> {self.to_user.username}"


class DirectMessage(models.Model):
    """1대1 메시지 모델"""

    sender = models.ForeignKey(
        User,
        related_name="sent_direct_messages",
        on_delete=models.CASCADE,
        help_text="메시지 발신자",
    )
    recipient = models.ForeignKey(
        User,
        related_name="received_direct_messages",
        on_delete=models.CASCADE,
        help_text="메시지 수신자",
    )
    content = models.TextField(help_text="메시지 내용")
    is_read = models.BooleanField(default=False, help_text="읽음 여부")
    created_at = models.DateTimeField(auto_now_add=True, help_text="메시지 생성 시간")

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read", "-created_at"]),
            models.Index(fields=["sender", "-created_at"]),
        ]

    def __str__(self):
        return (
            f"{self.sender.username} -> {self.recipient.username}: {self.content[:30]}"
        )


class LobbyMessage(models.Model):
    """로비 전체 채팅 메시지 모델"""

    user = models.ForeignKey(
        User,
        related_name="lobby_messages",
        on_delete=models.CASCADE,
        help_text="메시지 작성자",
    )
    content = models.TextField(help_text="메시지 내용")
    created_at = models.DateTimeField(auto_now_add=True, help_text="메시지 생성 시간")

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self):
        return f"{self.user.username}: {self.content[:30]}"


class Report(models.Model):
    """신고 모델"""

    REPORT_TYPE_CHOICES = [
        ("user", "유저 신고"),
        ("chat", "채팅 신고"),
        ("game", "게임 신고"),
    ]

    REASON_CHOICES = [
        ("abuse", "욕설/비하"),
        ("spam", "도배/스팸"),
        ("cheat", "핵/치팅 의심"),
        ("stalling", "고의 시간끌기"),
        ("inappropriate", "부적절한 행동"),
        ("other", "기타"),
    ]

    STATUS_CHOICES = [
        ("pending", "대기"),
        ("reviewed", "처리완료"),
        ("dismissed", "기각"),
    ]

    reporter = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="reports_filed",
        verbose_name="신고자",
    )
    reported_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="reports_received",
        verbose_name="피신고자",
    )
    report_type = models.CharField(
        max_length=10, choices=REPORT_TYPE_CHOICES, verbose_name="신고 유형"
    )
    reason = models.CharField(
        max_length=20, choices=REASON_CHOICES, verbose_name="신고 사유"
    )
    description = models.TextField(blank=True, verbose_name="상세 설명")
    evidence = models.TextField(blank=True, verbose_name="증거")
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="pending",
        verbose_name="처리 상태",
    )
    admin_note = models.TextField(blank=True, verbose_name="관리자 메모")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="신고 시간")
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="처리 시간")
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reports_reviewed",
        verbose_name="처리 관리자",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "신고"
        verbose_name_plural = "신고"
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["reported_user", "-created_at"]),
        ]

    def __str__(self):
        return f"[{self.get_status_display()}] {self.reporter} → {self.reported_user} ({self.get_reason_display()})"


class Sanction(models.Model):
    """제재 모델"""

    SANCTION_TYPE_CHOICES = [
        ("warning", "경고"),
        ("chat_ban", "채팅 금지"),
        ("suspend", "계정 정지"),
        ("permanent_ban", "영구 정지"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sanctions",
        verbose_name="제재 대상",
    )
    sanction_type = models.CharField(
        max_length=20, choices=SANCTION_TYPE_CHOICES, verbose_name="제재 유형"
    )
    reason = models.TextField(verbose_name="제재 사유")
    duration_days = models.IntegerField(null=True, blank=True, verbose_name="기간(일)")
    starts_at = models.DateTimeField(auto_now_add=True, verbose_name="시작 시간")
    ends_at = models.DateTimeField(null=True, blank=True, verbose_name="종료 시간")
    issued_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sanctions_issued",
        verbose_name="처리 관리자",
    )
    related_report = models.ForeignKey(
        Report,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sanctions",
        verbose_name="관련 신고",
    )

    class Meta:
        ordering = ["-starts_at"]
        verbose_name = "제재"
        verbose_name_plural = "제재"
        indexes = [
            models.Index(fields=["user", "-starts_at"]),
        ]

    def __str__(self):
        return f"{self.user} - {self.get_sanction_type_display()} ({self.reason[:30]})"

import os
import uuid

from django.conf import settings
from django.db import models


def profile_image_path(instance, filename):
    """프로필 이미지 저장 경로 생성 (UUID로 파일명 변경)"""
    ext = os.path.splitext(filename)[1].lower()
    new_filename = f"{uuid.uuid4().hex}{ext}"
    return f"profiles/{new_filename}"


# 레이팅 시스템 상수
INITIAL_RATING = 1000  # 초기 레이팅
MIN_RATING = 800  # 최소 레이팅
K_FACTOR = 32  # K-factor (레이팅 변동폭)

# 기본 프로필 아바타 색상 옵션
DEFAULT_AVATAR_CHOICES = [
    ("green", "초록"),
    ("blue", "파랑"),
    ("red", "빨강"),
    ("purple", "보라"),
    ("yellow", "노랑"),
    ("wood", "나무"),
    ("cyan", "하늘"),
    ("gray", "회색"),
]


def calculate_elo(winner_rating, loser_rating, k=K_FACTOR):
    """
    Elo 레이팅 계산
    Returns: (new_winner_rating, new_loser_rating, winner_change, loser_change)
    """
    # 예상 승률 계산
    expected_winner = 1 / (1 + 10 ** ((loser_rating - winner_rating) / 400))
    expected_loser = 1 - expected_winner

    # 새 레이팅 계산
    winner_change = round(k * (1 - expected_winner))
    loser_change = round(k * (0 - expected_loser))

    new_winner_rating = winner_rating + winner_change
    new_loser_rating = max(MIN_RATING, loser_rating + loser_change)  # 최소 레이팅 보장

    return new_winner_rating, new_loser_rating, winner_change, loser_change


class UserProfile(models.Model):
    """사용자 전적 프로필"""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    wins = models.IntegerField(default=0, verbose_name="승리")
    losses = models.IntegerField(default=0, verbose_name="패배")
    rating = models.IntegerField(default=INITIAL_RATING, verbose_name="레이팅")
    profile_image = models.ImageField(
        upload_to=profile_image_path,
        null=True,
        blank=True,
        verbose_name="프로필 이미지",
    )
    default_avatar = models.CharField(
        max_length=20,
        choices=DEFAULT_AVATAR_CHOICES,
        default="green",
        verbose_name="기본 아바타 색상",
    )
    chat_banned_until = models.DateTimeField(
        null=True, blank=True, verbose_name="채팅 금지 만료"
    )
    suspended_until = models.DateTimeField(
        null=True, blank=True, verbose_name="계정 정지 만료"
    )
    is_permanently_banned = models.BooleanField(default=False, verbose_name="영구 정지")

    class Meta:
        verbose_name = "사용자 프로필"
        verbose_name_plural = "사용자 프로필"

    def __str__(self):
        return f"{self.user.username} - {self.rating}점 ({self.wins}승 {self.losses}패)"

    @property
    def total_games(self):
        """총 게임 수"""
        return self.wins + self.losses

    @property
    def win_rate(self):
        """승률 (퍼센트)"""
        if self.total_games == 0:
            return 0.0
        return round((self.wins / self.total_games) * 100, 1)

    @property
    def profile_image_url(self):
        """프로필 이미지 URL (없으면 선택한 기본 아바타 색상)"""
        if self.profile_image:
            return self.profile_image.url
        color = self.default_avatar or "green"
        return f"/static/images/default_profile_{color}.svg"


class NicknameChangeLog(models.Model):
    """닉네임 변경 이력"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="nickname_changes",
    )
    old_nickname = models.CharField(max_length=30, blank=True)
    new_nickname = models.CharField(max_length=30)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-changed_at"]
        verbose_name = "닉네임 변경 이력"
        verbose_name_plural = "닉네임 변경 이력"

    def __str__(self):
        return f"{self.user.username}: {self.old_nickname} → {self.new_nickname}"

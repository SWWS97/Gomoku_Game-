from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    """사용자 전적 프로필"""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    wins = models.IntegerField(default=0, verbose_name="승리")
    losses = models.IntegerField(default=0, verbose_name="패배")

    class Meta:
        verbose_name = "사용자 프로필"
        verbose_name_plural = "사용자 프로필"

    def __str__(self):
        return f"{self.user.username} - {self.wins}승 {self.losses}패"

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

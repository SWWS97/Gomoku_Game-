from django.conf import settings
from django.db import models


class NicknameChangeLog(models.Model):
    """닉네임 변경 이력"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="nickname_changes"
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
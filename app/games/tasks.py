from datetime import timedelta

from celery import shared_task
from django.utils import timezone
from app.games.models import LobbyMessage


@shared_task
def delete_old_lobby_messages(hours: int = 24) -> str:
    """24시간이 지난 로비 메시지 삭제"""

    cutoff_time = timezone.now() - timedelta(hours=hours)
    old_messages = LobbyMessage.objects.filter(created_at__lt=cutoff_time)
    count = old_messages.count()
    old_messages.delete()

    return f"삭제 완료: {count}개 로비 메시지"
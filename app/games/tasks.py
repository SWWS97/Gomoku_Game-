from datetime import timedelta

from celery import shared_task
from django.utils import timezone


@shared_task
def delete_old_messages(hours: int = 24) -> str:
    """24시간이 지난 DirectMessage 삭제"""
    from app.games.models import DirectMessage

    cutoff_time = timezone.now() - timedelta(hours=hours)
    old_messages = DirectMessage.objects.filter(created_at__lt=cutoff_time)
    count = old_messages.count()
    old_messages.delete()

    return f"삭제 완료: {count}개 메시지"
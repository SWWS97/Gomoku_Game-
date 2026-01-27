from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from app.games.models import DirectMessage


class Command(BaseCommand):
    help = "24시간이 지난 DirectMessage 삭제"

    def add_arguments(self, parser):
        parser.add_argument(
            "--hours",
            type=int,
            default=24,
            help="삭제 기준 시간 (기본값: 24시간)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="실제 삭제 없이 삭제될 메시지 수만 출력",
        )

    def handle(self, *args, **options):
        hours = options["hours"]
        dry_run = options["dry_run"]

        cutoff_time = timezone.now() - timedelta(hours=hours)
        old_messages = DirectMessage.objects.filter(created_at__lt=cutoff_time)
        count = old_messages.count()

        if dry_run:
            self.stdout.write(f"[DRY RUN] 삭제 대상 메시지: {count}개")
        else:
            old_messages.delete()
            self.stdout.write(self.style.SUCCESS(f"삭제 완료: {count}개 메시지"))

import os

from celery import Celery

# Django 설정 모듈 지정
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("gomoku")

# Django settings에서 CELERY_ 접두사로 시작하는 설정 읽기
app.config_from_object("django.conf:settings", namespace="CELERY")

# 등록된 Django 앱에서 tasks.py 자동 탐색
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")

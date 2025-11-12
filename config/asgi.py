# config/asgi.py
import os
from pathlib import Path

# (필수) settings 지정이 가장 먼저
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# (선택) .env.prod 로드가 필요하면 여기서
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env.prod")
except Exception:
    pass

# 1) 먼저 Django를 부팅해서 app registry를 올림
from django.core.asgi import get_asgi_application

django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack

# 2) 그 다음에 Channels 관련 것들을 import (여기서 consumers/routing이 모델 import해도 OK)
from channels.routing import ProtocolTypeRouter, URLRouter

from app.games.utils.routing import websocket_urlpatterns

# 3) 최종 application
application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
    }
)

# config/settings.py
import os
from pathlib import Path

import environ

# ──────────────────────────────────────────────────────────────────────
# 기본 경로 / env 로딩
# ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent

# django-environ 초기화
env = environ.Env()

# .env 경로 우선순위: envs/.env.prod → envs/.env → 프로젝트 루트 .env
for candidate in ("envs/.env.prod", "envs/.env", ".env"):
    fp = BASE_DIR / candidate
    if fp.exists():
        environ.Env.read_env(fp)
        break
# (특정 경로를 강제하고 싶다면 ENV_FILE=/절대/경로 형태로 넘겨도 됩니다)
if os.getenv("ENV_FILE"):
    custom = Path(os.getenv("ENV_FILE"))
    environ.Env.read_env(custom if custom.is_absolute() else (BASE_DIR / custom))

# ──────────────────────────────────────────────────────────────────────
# 핵심 설정
# ──────────────────────────────────────────────────────────────────────
SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-not-safe")
DEBUG = env.bool("DJANGO_DEBUG", default=False)

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["127.0.0.1", "localhost"])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# ──────────────────────────────────────────────────────────────────────
# 앱
# ──────────────────────────────────────────────────────────────────────
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "channels",
    "whitenoise.runserver_nostatic",  # runserver 때도 whitenoise로 일관
]

OWN_APPS = [
    "app.games",
    "app.accounts",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + OWN_APPS

# ──────────────────────────────────────────────────────────────────────
# 미들웨어
# ──────────────────────────────────────────────────────────────────────
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # 정적파일 서빙 (nginx 없이 운영 가능)
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# ──────────────────────────────────────────────────────────────────────
# URL / ASGI / WSGI
# ──────────────────────────────────────────────────────────────────────
ROOT_URLCONF = "config.urls"
ASGI_APPLICATION = "config.asgi.application"
WSGI_APPLICATION = "config.wsgi.application"

# ──────────────────────────────────────────────────────────────────────
# 템플릿
# ──────────────────────────────────────────────────────────────────────
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ──────────────────────────────────────────────────────────────────────
# 데이터베이스
#   - 컨테이너 환경: POSTGRES_* 값이 있으면 Postgres 사용
#   - 아니면 SQLite 사용 (로컬 편의)
# ──────────────────────────────────────────────────────────────────────
if env("POSTGRES_DB", default=None):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("POSTGRES_DB"),
            "USER": env("POSTGRES_USER"),
            "PASSWORD": env("POSTGRES_PASSWORD"),
            "HOST": env("POSTGRES_HOST", default="db"),
            "PORT": env("POSTGRES_PORT", default="5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# ──────────────────────────────────────────────────────────────────────
# Channels (Redis 사용 시)
#   REDIS_URL 예: redis://redis:6379/0
#   미설정 시 InMemory 레이어(단일 프로세스용)
# ──────────────────────────────────────────────────────────────────────
REDIS_URL = env("REDIS_URL", default=None)
if REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [REDIS_URL]},
        }
    }
else:
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

# ──────────────────────────────────────────────────────────────────────
# 인증/국제화
# ──────────────────────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = env("LANGUAGE_CODE", default="ko-kr")
TIME_ZONE = env("TIME_ZONE", default="Asia/Seoul")
USE_I18N = True
USE_TZ = True

# ──────────────────────────────────────────────────────────────────────
# 정적 파일 (whitenoise)
#   collectstatic 시 STATIC_ROOT 로 수집
# ──────────────────────────────────────────────────────────────────────
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ──────────────────────────────────────────────────────────────────────
# 기타
# ──────────────────────────────────────────────────────────────────────
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# 로그인/리다이렉트
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/games/new/"
LOGOUT_REDIRECT_URL = "/accounts/login/"

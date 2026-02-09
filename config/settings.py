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

# .env 경로 우선순위: envs/.env.dev → envs/.env.prod
for candidate in ("envs/.env.dev", "envs/.env.prod"):
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

# nginx 뒤에서 HTTPS 인식을 위한 설정
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

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
    "storages",  # django-storages (Oracle Object Storage)
    # django-allauth
    "django.contrib.sites",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    # 소셜 프로바이더
    "allauth.socialaccount.providers.naver",
    "allauth.socialaccount.providers.kakao",
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
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",  # django-allauth 필수 미들웨어
    "app.accounts.middleware.SuspensionCheckMiddleware",
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
    # Redis 캐시 (온라인 유저 추적용)
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
        }
    }
else:
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
    # 로컬 메모리 캐시 (개발용)
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "unique-snowflake",
        }
    }

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
# 정적 파일 (Nginx가 직접 서빙)
#   collectstatic 시 STATIC_ROOT 로 수집
# ──────────────────────────────────────────────────────────────────────
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [
    BASE_DIR / "static",  # 프로젝트 루트의 static 폴더
]

# ──────────────────────────────────────────────────────────────────────
# 미디어 파일 (Oracle Object Storage - S3 호환)
#   프로필 이미지 등 사용자 업로드 파일
# ──────────────────────────────────────────────────────────────────────
# Oracle Object Storage 설정
OCI_ACCESS_KEY = env("OCI_ACCESS_KEY", default="")
OCI_SECRET_KEY = env("OCI_SECRET_KEY", default="")
OCI_BUCKET_NAME = env("OCI_BUCKET_NAME", default="omokjomok-media")
OCI_NAMESPACE = env("OCI_NAMESPACE", default="")
OCI_REGION = env("OCI_REGION", default="ap-chuncheon-1")

if OCI_ACCESS_KEY and OCI_SECRET_KEY and OCI_NAMESPACE:
    # Oracle Object Storage 사용 (S3 호환 API)
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
            "OPTIONS": {
                "access_key": OCI_ACCESS_KEY,
                "secret_key": OCI_SECRET_KEY,
                "bucket_name": OCI_BUCKET_NAME,
                "endpoint_url": f"https://{OCI_NAMESPACE}.compat.objectstorage.{OCI_REGION}.oraclecloud.com",
                "region_name": OCI_REGION,
                "default_acl": "public-read",
                "querystring_auth": False,  # URL에 인증 파라미터 제외 (public 접근)
            },
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
    MEDIA_URL = f"https://{OCI_NAMESPACE}.compat.objectstorage.{OCI_REGION}.oraclecloud.com/{OCI_BUCKET_NAME}/"
else:
    # 로컬 개발 환경: 파일시스템 사용
    MEDIA_URL = "/media/"
    MEDIA_ROOT = BASE_DIR / "media"

# ──────────────────────────────────────────────────────────────────────
# 기타
# ──────────────────────────────────────────────────────────────────────
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# 로그인/리다이렉트
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/games/"  # 로비로 리다이렉트
LOGOUT_REDIRECT_URL = "/accounts/login/"

# ──────────────────────────────────────────────────────────────────────
# django-allauth 설정
# ──────────────────────────────────────────────────────────────────────
# SITE_ID: 1=로컬(127.0.0.1:8000), 2=프로덕션(www.gomoku.co.kr)
SITE_ID = env.int("SITE_ID", default=1)

AUTHENTICATION_BACKENDS = [
    # Django 기본 인증 (username/password)
    "django.contrib.auth.backends.ModelBackend",
    # allauth 소셜 로그인
    "allauth.account.auth_backends.AuthenticationBackend",
]

# allauth 설정
ACCOUNT_EMAIL_VERIFICATION = "none"  # 이메일 인증 비활성화
ACCOUNT_EMAIL_REQUIRED = True  # 이메일 필수 (비밀번호 재설정용)
ACCOUNT_UNIQUE_EMAIL = True  # 이메일 중복 불가 (같은 이메일로 여러 계정 방지)
ACCOUNT_USERNAME_REQUIRED = False  # Username 필수 아님 (소셜 로그인 시 자동 생성)
ACCOUNT_LOGIN_METHODS = ["username", "email"]  # username 또는 email로 로그인 가능
ACCOUNT_SIGNUP_FIELDS = [
    "email*",
    "username*",
    "password1*",
    "password2*",
]  # 일반 회원가입 필수 필드
SOCIALACCOUNT_AUTO_SIGNUP = False  # 소셜 로그인 시 닉네임 입력받기 위해 False
SOCIALACCOUNT_LOGIN_ON_GET = True  # GET 요청으로 바로 로그인 (콜백 처리)
SOCIALACCOUNT_QUERY_EMAIL = True  # 소셜 로그인 시 이메일 정보 요청
SOCIALACCOUNT_EMAIL_REQUIRED = True  # 소셜 로그인 시 이메일 필수
SOCIALACCOUNT_AUTO_CONNECT = True  # 같은 이메일이면 기존 계정에 자동 연동

# 커스텀 Adapter 및 Form 설정
ACCOUNT_ADAPTER = "app.accounts.adapters.CustomAccountAdapter"
SOCIALACCOUNT_ADAPTER = "app.accounts.adapters.CustomSocialAccountAdapter"
SOCIALACCOUNT_FORMS = {"signup": "app.accounts.forms.SocialSignupForm"}

# 소셜 로그인 프로바이더 설정 (환경 변수 방식)
SOCIALACCOUNT_PROVIDERS = {
    "naver": {
        "APP": {
            "client_id": env("NAVER_CLIENT_ID", default=""),
            "secret": env("NAVER_SECRET", default=""),
        }
    },
    "kakao": {
        "APP": {
            "client_id": env("KAKAO_CLIENT_ID", default=""),
            "secret": env("KAKAO_SECRET", default=""),
        }
    },
}

# ──────────────────────────────────────────────────────────────────────
# 이메일 설정 (개발 환경에서는 콘솔로 출력)
# ──────────────────────────────────────────────────────────────────────
if DEBUG:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    # 프로덕션에서도 이메일 인증을 사용하지 않으므로 콘솔로 설정
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# ──────────────────────────────────────────────────────────────────────
# Celery 설정
# ──────────────────────────────────────────────────────────────────────
CELERY_BROKER_URL = REDIS_URL or "redis://localhost:6379/0"
CELERY_RESULT_BACKEND = REDIS_URL or "redis://localhost:6379/0"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

# Celery Beat 스케줄 설정
CELERY_BEAT_SCHEDULE = {
    "delete-old-lobby-messages-every-hour": {
        "task": "app.games.tasks.delete_old_lobby_messages",
        "schedule": 60 * 60,  # 매 시간 (3600초)
    },
}

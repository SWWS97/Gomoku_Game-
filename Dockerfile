# ---- base python image
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# OS deps (psycopg2, Pillow 등 빌드용)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev pkg-config curl git \
    libjpeg62-turbo-dev zlib1g-dev \
 && rm -rf /var/lib/apt/lists/*

# uv 설치
RUN pip install --upgrade pip && pip install uv

# 디렉토리(default)설정
WORKDIR /app

# 의존성 명세만 먼저 복사 → 레이어 캐시 최적화
COPY pyproject.toml ./

# 컨테이너(리눅스/3.12) 기준으로 락 생성/정렬
RUN uv lock --python 3.12 --upgrade

# 🔑 uv로 requirements 생성 → 시스템(site-packages)에 설치
RUN uv export --frozen --no-dev --format requirements-txt > /tmp/req.txt \
 && pip install -r /tmp/req.txt

# 앱 소스 복사(현재경로에 존재하는 모든 소스파일을 이미지에 복사)
COPY . .

# (선택) STATIC_ROOT 경로와 일치하도록 폴더 보장
RUN mkdir -p /app/static

# 문서/네트워크용 포트 선언 (실제 공개는 compose의 ports로)
EXPOSE 8000

# 운영 커맨드 (dev에선 compose에서 runserver로 덮어쓰기)
CMD ["sh","-c","python manage.py migrate && python manage.py collectstatic --noinput || true && daphne -b 0.0.0.0 -p 8000 config.asgi:application"]
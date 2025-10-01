# ---- base python image
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# OS deps (psycopg2-binary 안 쓰면 libpq-dev 필요)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
 && rm -rf /var/lib/apt/lists/*

# ---- install uv (lockfile 기반 설치용)
RUN pip install --upgrade pip && pip install uv

WORKDIR /app

# 의존성 파일만 먼저 복사 → 레이어 캐시 최대화
COPY pyproject.toml uv.lock ./

# uv.lock을 requirements.txt로 내보내고 시스템에 설치
# (uv가 컨테이너 안에서 프로젝트를 editable로 설치하진 않게 함)
RUN uv export --no-dev --format requirements-txt > /tmp/req.txt \
 && pip install -r /tmp/req.txt

# 앱 소스 복사
COPY . .

# (선택) 정적파일 폴더 보장
RUN mkdir -p /app/static

# 컨테이너 기본 실행 커맨드(Compose에서 덮어써도 무관)
CMD ["sh", "-c", "python manage.py migrate && python manage.py collectstatic --noinput || true && daphne -b 0.0.0.0 -p 8000 config.asgi:application"]
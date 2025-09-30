# 1) 베이스 이미지
FROM python:3.12-slim

# 2) 시스템 패키지 (빌드/psycopg 필요시)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl libpq-dev \
 && rm -rf /var/lib/apt/lists/*

# 3) uv 설치 (공식 스크립트)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# 4) 작업 디렉토리
WORKDIR /app

# 5) 의존성만 먼저 복사 → 캐시층
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

# 6) 앱 코드 복사
COPY . .

# 7) (선택) 정적파일 수집이 있다면:
# RUN .venv/bin/python manage.py collectstatic --noinput

# 8) 기본 포트
EXPOSE 8000

# 9) 실행 커맨드(운영: daphne)
CMD [".venv/bin/daphne", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]
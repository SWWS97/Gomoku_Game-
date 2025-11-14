# ----------------------------------------------------------------------
# 🔹 스테이지 1: 'builder'
# - 여기서는 패키지 빌드에 필요한 모든 도구(-dev, build-essential)를 설치합니다.
# - 최종 이미지에는 포함되지 않습니다.
# ----------------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# OS deps (psycopg2, Pillow 등 빌드용 도구 전부)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev pkg-config curl git \
    libjpeg62-turbo-dev zlib1g-dev \# ----------------------------------------------------------------------
# 🔹 스테이지 1: 'builder'
# - 여기서는 패키지 빌드에 필요한 모든 도구(-dev, build-essential)를 설치합니다.
# - 최종 이미지에는 포함되지 않습니다.
# ----------------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# OS deps (psycopg2, Pillow 등 빌드용 도구 전부)
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
# 이 패키지들은 /usr/local/lib/python3.12/site-packages/ 에 설치됩니다.
RUN uv export --frozen --no-dev --format requirements-txt > /tmp/req.txt \
 && pip install -r /tmp/req.txt

# (빌더 스테이지에서는 앱 소스 코드(COPY . .)가 필요 없습니다)


# ----------------------------------------------------------------------
# 🔹 스테이지 2: 'runtime' (최종 이미지)
# - 다시 깨끗한 python:3.12-slim 이미지에서 시작합니다.
# - 여기에는 빌드 도구를 설치하지 않고, "실행"에 필요한 최소한의 라이브러리만 설치합니다.
# ----------------------------------------------------------------------
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# ❗️ 런타임에 "필요한" OS 라이브러리만 설치합니다.
# (예: libpq-dev -> libpq5, libjpeg62-turbo-dev -> libjpeg62-turbo)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libjpeg62-turbo \
    zlib1g \
 && rm -rf /var/lib/apt/lists/*

# 디렉토리(default)설정
WORKDIR /app

# ❗️ [핵심] 'builder' 스테이지에서 설치했던 Python 패키지들만 복사해옵니다.
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages

# ❗️ 'builder' 스테이지에서 설치된 실행 파일(daphne, django-admin 등)도 복사합니다.
COPY --from=builder /usr/local/bin /usr/local/bin

# 앱 소스 복사 (최종 이미지에만 소스 코드를 복사)
COPY . .

# (선택) STATIC_ROOT 경로와 일치하도록 폴더 보장
RUN mkdir -p /app/static

# 문서/네트워크용 포트 선언 (실제 공개는 compose의 ports로)
EXPOSE 8000

# 운영 커맨드 (dev에선 compose에서 runserver로 덮어쓰기)
# (동일하게 유지)
CMD ["sh","-c","python manage.py migrate && python manage.py collectstatic --noinput || true && daphne -b 0.0.0.0 -p 8000 config.asgi:application"]
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
# 이 패키지들은 /usr/local/lib/python3.12/site-packages/ 에 설치됩니다.
RUN uv export --frozen --no-dev --format requirements-txt > /tmp/req.txt \
 && pip install -r /tmp/req.txt

# (빌더 스테이지에서는 앱 소스 코드(COPY . .)가 필요 없습니다)


# ----------------------------------------------------------------------
# 🔹 스테이지 2: 'runtime' (최종 이미지)
# - 다시 깨끗한 python:3.12-slim 이미지에서 시작합니다.
# - 여기에는 빌드 도구를 설치하지 않고, "실행"에 필요한 최소한의 라이브러리만 설치합니다.
# ----------------------------------------------------------------------
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# ❗️ 런타임에 "필요한" OS 라이브러리만 설치합니다.
# (예: libpq-dev -> libpq5, libjpeg62-turbo-dev -> libjpeg62-turbo)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libjpeg62-turbo \
    zlib1g \
 && rm -rf /var/lib/apt/lists/*

# 디렉토리(default)설정
WORKDIR /app

# ❗️ [핵심] 'builder' 스테이지에서 설치했던 Python 패키지들만 복사해옵니다.
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages

# ❗️ 'builder' 스테이지에서 설치된 실행 파일(daphne, django-admin 등)도 복사합니다.
COPY --from=builder /usr/local/bin /usr/local/bin

# 앱 소스 복사 (최종 이미지에만 소스 코드를 복사)
COPY . .

# (선택) STATIC_ROOT 경로와 일치하도록 폴더 보장
RUN mkdir -p /app/static

# 문서/네트워크용 포트 선언 (실제 공개는 compose의 ports로)
EXPOSE 8000

# 운영 커맨드 (dev에선 compose에서 runserver로 덮어쓰기)
# (동일하게 유지)
CMD ["sh","-c","python manage.py migrate && python manage.py collectstatic --noinput || true && daphne -b 0.0.0.0 -p 8000 config.asgi:application"]
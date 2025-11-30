# 🎲파이썬 오목 게임🎲

## 📂 Local 실행 명령어
#### muv run daphne -b 0.0.0.0 -p 8000 config.asgi:application

## 📂 Local DB(postgreSQL) 생성 명령어
#### psql -U postgres
#### CREATE USER myuser WITH PASSWORD 'mypassword';
#### CREATE DATABASE mydb OWNER myuser;
#### \du     -- 유저 목록 확인
#### \l      -- 데이터베이스 목록 확인

## 📂 Makefile 단축 명령어 모음
#### make dev              # 로컬 개발(Daphne) 시작
#### make migrate         # 로컬 DB 마이그레이션
#### make compose-up-dev       # 도커(개발) 기동
#### make compose-migrate-dev  # 개발 DB 마이그레이션
#### make compose-up-prod       # 도커(스테이징/운영) 기동
#### make compose-migrate-prod  # 운영 DB 마이그레이션

## 📁 EC2 콘솔에서 DB 내용 확인하는 명렁어
#### 서비스 위치 : /srv/gomoku
#### docker compose exec db psql -U omokuser -d omokdb
#### \l      -- DB 리스트 확인
#### \dt     -- 테이블 목록 확인
#### 예) SELECT * FROM auth_user LIMIT 5;   -- 장고 기본 user 테이블 확인

## 📁 로컬 터미널에서 접속 명렁어
#### chmod 600 ~/.ssh/만든 키페어.pem
#### ssh -i ~/.ssh/만든 키페어.pem ubuntu@EC2 퍼블릭 IP

## 📋 프로젝트 개요

Django 기반 실시간 오목 게임 (렌주 규칙 적용)
  - WebSocket을 통한 실시간 멀티플레이어 지원
  - Django Channels + Redis + Daphne 사용

### 🗂️ 주요 디렉토리 구조

  gomoku_game/
  ├── app/
  │   ├── games/          # 게임 로직, WebSocket 처리
  │   │   ├── models.py   # Game, Move 모델 (15x15 보드)
  │   │   ├── utils/
  │   │   │   ├── consumers.py  # WebSocket 컨슈머
  │   │   │   ├── omok.py       # 렌주 규칙 엔진 (33, 44, 장목 금지)
  │   │   │   └── routing.py    # WebSocket 라우팅
  │   │   └── tests/      # 게임 규칙 테스트
  │   └── accounts/       # 회원가입/로그인
  ├── config/             # Django 설정
  │   ├── settings.py     # 환경 기반 설정 (PostgreSQL/SQLite)
  │   ├── asgi.py         # ASGI + WebSocket 라우팅
  │   └── urls.py         # URL 매핑
  ├── templates/          # HTML 템플릿
  ├── envs/              # 환경 변수 (.env.dev, .env.prod)
  └── Dockerfile         # 멀티스테이지 Docker 빌드

###  🛠️ 기술 스택

  | 영역        | 기술                         |
  |-----------|----------------------------|
  | 백엔드       | Django 5.0 + Channels 4.x  |
  | WebSocket | Daphne (ASGI 서버)           |
  | 메시지 브로커   | Redis 7.0                  |
  | DB (개발)   | SQLite                     |
  | DB (프로덕션) | PostgreSQL 16              |
  | 프론트엔드     | Vanilla JS + WebSocket API |
  | 패키지 매니저   | UV                         |
  | 컨테이너      | Docker Compose             |

### ⚙️ 핵심 기능

  1. 실시간 게임 - WebSocket 기반 양방향 통신
  2. 렌주 규칙 - 흑돌 33, 44, 장목 금지 규칙 구현
  3. 이동 기록 - Move 모델로 게임 리플레이 가능
  4. 보드 저장 - 225자 문자열로 압축 저장 (15x15)
  5. 동시성 제어 - select_for_update()로 race condition 방지
  6. 소셜 로그인 - 네이버, 카카오 OAuth 연동 (django-allauth)

### 🎯 아키텍처 특징

  - 비동기 우선: AsyncJsonWebsocketConsumer 사용
  - 환경 분리: .env.dev / .env.prod로 설정 분리
  - Atomic 트랜잭션: 규칙 검증과 DB 업데이트를 하나의 트랜잭션으로
  - 정적 파일: WhiteNoise로 처리 (Nginx 불필요)

### 🔐 소셜 로그인 설정

  네이버 및 카카오 소셜 로그인 설정 방법은 [SOCIAL_LOGIN_SETUP.md](./SOCIAL_LOGIN_SETUP.md) 문서를 참고하세요.
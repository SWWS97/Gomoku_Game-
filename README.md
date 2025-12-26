# 🎲 Gomoku Game (오목 게임) 🎲

Django 기반 실시간 오목 게임 (렌주 규칙 적용)

## 📋 프로젝트 개요

WebSocket을 활용한 실시간 멀티플레이어 오목 게임입니다.
- 렌주 룰 (흑 금수: 33, 44, 장목) 적용
- 소셜 로그인 (네이버, 카카오) 지원
- 타이머, 리매치, 로비 채팅 등 다양한 부가 기능 제공
- 모바일 반응형 디자인

## 🛠️ 기술 스택

| 영역        | 기술                         |
|-----------|----------------------------|
| 백엔드       | Django 5.0 + Channels 4.x  |
| WebSocket | Daphne (ASGI 서버)           |
| 메시지 브로커   | Redis 7.0                  |
| DB        | PostgreSQL 16 (AWS RDS)    |
| 프론트엔드     | Vanilla JS + WebSocket API |
| 소셜 로그인    | django-allauth             |
| 패키지 매니저   | UV                         |
| 컨테이너      | Docker Compose             |
| 배포        | AWS EC2 + Nginx            |

## ⚙️ 주요 기능

### 🎮 게임 시스템
- **렌주 규칙 엔진**
  - 흑돌 33 금수 (쌍삼 금지)
  - 흑돌 44 금수 (쌍사 금지)
  - 흑돌 장목 금수 (6목 이상 금지)
  - 흑은 정확히 5목만 승리, 백은 5목 이상 승리

- **실시간 멀티플레이어**
  - WebSocket 양방향 통신
  - 동시 착수 방지 (select_for_update)
  - 실시간 상태 동기화

- **타이머 시스템**
  - 플레이어당 15분 제한
  - 턴별 시간 차감
  - 30초 이하 경고 표시
  - 시간 초과 시 자동 패배

- **게임 룸 관리**
  - 커스텀 방 제목 설정
  - 대기 중인 방 목록 표시
  - 방 생성자가 나가면 자동 삭제

### 🔄 게임 플레이 기능
- **준비 시스템**
  - 양쪽 플레이어 모두 준비 완료 필요
  - 방장이 게임 시작 버튼 활성화

- **리매치 시스템**
  - 게임 종료 후 같은 방에서 재경기 가능
  - 양쪽 동의 시 게임판 리셋

- **착수 표시**
  - 마지막 착수 위치 반짝이는 애니메이션
  - 황금색 강조 효과 (3회 반복)

- **효과음**
  - 착수 시 "딱" 소리
  - 플레이어 입장 시 "띠링~" 벨 소리

### 👥 사용자 기능
- **소셜 로그인**
  - 네이버 OAuth 2.0
  - 카카오 OAuth 2.0
  - 닉네임 중복 체크

- **프로필 관리**
  - 닉네임 변경 (24시간 1회 제한)
  - 닉네임 중복 검사
  - 비밀번호 변경
  - 변경 이력 추적 (NicknameChangeLog)

- **전적 조회**
  - 승/패/무 통계
  - 게임 히스토리 저장

### 💬 커뮤니티 기능
- **로비 채팅**
  - 실시간 전체 채팅
  - 욕설 필터링
  - 접속자 목록 표시
  - 모바일 친화적 UI (토글 버튼)

### 📱 UI/UX
- **반응형 디자인**
  - 데스크톱/태블릿/모바일 최적화
  - 모바일 터치 영역 확대
  - 키보드 대응 (채팅창 유지)

- **애니메이션**
  - 모달 페이드인
  - 타이머 펄스 효과
  - 버튼 호버/액티브 효과
  - 채팅창 슬라이드

## 🗂️ 프로젝트 구조

```
gomoku_game/
├── app/
│   ├── games/              # 게임 로직
│   │   ├── models.py       # Game, GameHistory, Move
│   │   ├── views.py        # 로비, 방 생성/참가, 전적 조회
│   │   ├── utils/
│   │   │   ├── consumers.py    # WebSocket 핸들러 (GameConsumer, LobbyConsumer)
│   │   │   ├── omok.py         # 렌주 규칙 엔진
│   │   │   └── routing.py      # WebSocket 라우팅
│   │   └── tests/
│   │       └── test_omok_rules.py  # 금수 규칙 테스트
│   └── accounts/           # 사용자 관리
│       ├── models.py       # NicknameChangeLog
│       ├── forms.py        # SignUpForm, SocialSignupForm, ProfileEditForm
│       ├── views.py        # 회원가입, 프로필 수정
│       └── adapter.py      # 소셜 로그인 어댑터
├── config/
│   ├── settings.py         # Django 설정 (환경 변수 기반)
│   ├── asgi.py            # ASGI + WebSocket 라우팅
│   └── urls.py            # URL 매핑
├── templates/
│   ├── games/
│   │   ├── lobby.html      # 로비 (방 목록, 채팅)
│   │   ├── room.html       # 게임 룸 (오목판, 타이머)
│   │   └── history.html    # 전적 조회
│   └── account/
│       ├── signup.html     # 회원가입
│       └── profile_edit.html  # 프로필 수정
├── envs/                  # 환경 변수
│   ├── .env.dev           # 로컬 개발
│   └── .env.prod          # 프로덕션
├── docker-compose.dev.yml
├── docker-compose.prod.yml
├── Dockerfile
├── Makefile
└── README.md
```

## 🚀 빠른 시작

### 로컬 개발 환경

#### 1. 의존성 설치
```bash
uv sync
```

#### 2. 환경 변수 설정
```bash
cp envs/.env.dev.example envs/.env.dev
# envs/.env.dev 파일 편집 (DB, Redis, Secret Key 등)
```

#### 3. DB 마이그레이션
```bash
make migrate
```

#### 4. 개발 서버 실행
```bash
make dev
# 또는: uv run daphne -b 0.0.0.0 -p 8000 config.asgi:application
```

#### 5. Redis 실행 (별도 터미널)
```bash
redis-server
```

브라우저에서 `http://localhost:8000` 접속

### Docker Compose로 실행

#### 개발 환경
```bash
make compose-up-dev
make compose-migrate-dev
```

#### 프로덕션 환경
```bash
make compose-up-prod
make compose-migrate-prod
```

## 📂 Makefile 단축 명령어

```bash
make dev                    # 로컬 개발 서버 시작 (Daphne)
make migrate               # 로컬 DB 마이그레이션
make compose-up-dev        # Docker (개발) 기동
make compose-migrate-dev   # 개발 DB 마이그레이션
make compose-up-prod       # Docker (프로덕션) 기동
make compose-migrate-prod  # 프로덕션 DB 마이그레이션
```

## 💾 데이터베이스 관리

### 로컬 PostgreSQL 설정
```bash
psql -U postgres
CREATE USER myuser WITH PASSWORD 'mypassword';
CREATE DATABASE mydb OWNER myuser;
\du     # 유저 목록 확인
\l      # 데이터베이스 목록 확인
```

### EC2 프로덕션 DB 접근
```bash
# 서비스 위치: /srv/gomoku
docker compose exec db psql -U omokuser -d omokdb

# DB 확인
\l      # DB 리스트
\dt     # 테이블 목록
SELECT * FROM auth_user LIMIT 5;
SELECT * FROM games_game WHERE winner IS NOT NULL LIMIT 10;
```

## 🔐 소셜 로그인 설정

네이버 및 카카오 소셜 로그인 설정 방법은 [SOCIAL_LOGIN_SETUP.md](./SOCIAL_LOGIN_SETUP.md) 문서를 참고하세요.

환경 변수에 다음 값 설정 필요:
```env
NAVER_CLIENT_ID=your_naver_client_id
NAVER_SECRET=your_naver_secret
KAKAO_REST_API_KEY=your_kakao_rest_api_key
```

## 🧪 테스트 실행

```bash
# 전체 테스트
uv run python manage.py test

# 오목 규칙 테스트만
uv run python manage.py test app.games.tests.test_omok_rules
```

## 🌐 배포 (AWS EC2)

### SSH 접속
```bash
chmod 600 ~/.ssh/your-keypair.pem
ssh -i ~/.ssh/your-keypair.pem ubuntu@YOUR_EC2_IP
```

### 배포 스크립트
```bash
cd /srv/gomoku
git pull origin main
docker compose down
docker compose up -d --build
docker compose exec web python manage.py migrate
```

## 🎯 아키텍처 특징

- **비동기 우선**: AsyncJsonWebsocketConsumer로 WebSocket 처리
- **환경 분리**: .env.dev / .env.prod로 설정 완전 분리
- **Atomic 트랜잭션**: 금수 검증과 DB 업데이트를 하나의 트랜잭션으로 처리
- **동시성 제어**: select_for_update()로 race condition 방지
- **정적 파일**: WhiteNoise로 처리 (Nginx 불필요)
- **무상태 설계**: WebSocket 연결마다 독립적 상태 관리

## 📝 핵심 로직

### 금수 판정 흐름
1. 클라이언트가 착수 요청 (x, y 좌표)
2. GameConsumer에서 수신
3. 흑돌인 경우 금수 검증:
   - `is_overline()` - 장목 체크
   - `is_forbidden_double_four()` - 44 체크
   - `is_forbidden_double_three()` - 33 체크
4. 금수가 아니면 착수 진행
5. 승리 조건 확인:
   - 흑: `has_exact_five()` (정확히 5목)
   - 백: `check_five()` (5목 이상)
6. broadcast_state()로 모든 클라이언트에 상태 전송

### 타이머 시스템
1. 게임 시작 시 각 플레이어 15분 (900초)
2. 턴마다 클라이언트 타이머 1초씩 감소
3. 착수 시 서버에서 시간 재계산
4. 시간 초과 시 자동 패배 처리

## 🐛 알려진 이슈 및 제한사항

- 관전 모드 미지원 (추후 추가 예정)
- 게임 리플레이 기능 미구현
- 채팅 메시지 저장 안 됨 (휘발성)

## 👨‍💻 개발자

- 개발: [SW]
- 버전: 1.0.0
- 최종 업데이트: 2025-12-26
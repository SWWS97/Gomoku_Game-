# 🎲 파이썬 오목 게임 🎲

## 📂 Local 실행 명령어
#### muv run daphne -b 0.0.0.0 -p 8000 config.asgi:application
## Local DB(postgreSQL)
#### psql -U postgres
#### CREATE USER myuser WITH PASSWORD 'mypassword';
#### CREATE DATABASE mydb OWNER myuser;
#### \du     -- 유저 목록 확인
#### \l      -- 데이터베이스 목록 확인

## 📂 Makefile 단축 명령어 모음
#### make dev              # 로컬 개발(Daphne) 시작
#### make migrate          # 로컬 DB 마이그레이션
#### make compose-up       # 도커(스테이징/운영) 기동
#### make compose-migrate  # 운영 DB 마이그레이션

## EC2 콘솔에서 DB 내용 확인하는 명렁어
#### docker compose exec db psql -U omokuser -d omokdb
#### \l      -- DB 리스트 확인
#### \dt     -- 테이블 목록 확인
#### 예) SELECT * FROM auth_user LIMIT 5;   -- 장고 기본 user 테이블 확인
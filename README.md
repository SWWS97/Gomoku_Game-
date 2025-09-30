# 🎲 파이썬 오목 게임 🎲

## 📂 Local 실행 명령어
#### muv run daphne -b 0.0.0.0 -p 8000 config.asgi:application

## 📂 Makefile 단축 명령어 모음
#### make dev              # 로컬 개발(Daphne) 시작
#### make migrate          # 로컬 DB 마이그레이션
#### make compose-up       # 도커(스테이징/운영) 기동
#### make compose-migrate  # 운영 DB 마이그레이션
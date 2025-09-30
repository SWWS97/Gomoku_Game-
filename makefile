SHELL := /bin/sh

# ----- 공통 변수 -----
DEV_ENV := .env.dev
PROD_ENV := .env.prod

DJANGO := uv run python manage.py
DAPHNE := uv run daphne -b 0.0.0.0 -p 8000 config.asgi:application

# ----- 로컬 개발 -----
.PHONY: dev
dev:        ## 로컬 개발: Daphne + .env.dev
	ENV_FILE=$(DEV_ENV) $(DAPHNE)

.PHONY: migrate
migrate:    ## 로컬 개발 DB 마이그레이션
	ENV_FILE=$(DEV_ENV) $(DJANGO) migrate

.PHONY: super
super:      ## 로컬 개발 슈퍼유저 생성
	ENV_FILE=$(DEV_ENV) $(DJANGO) createsuperuser

.PHONY: collect
collect:    ## 로컬 정적파일 수집(필요시)
	ENV_FILE=$(DEV_ENV) $(DJANGO) collectstatic --noinput

# ----- 도커(스테이징/운영) -----
.PHONY: compose-up
compose-up: ## docker-compose로 서비스 기동
	docker compose --env-file $(PROD_ENV) up -d --build

.PHONY: compose-logs
compose-logs: ## docker-compose 로그 보기
	docker compose logs -f

.PHONY: compose-migrate
compose-migrate: ## 컨테이너 안에서 마이그레이션
	docker compose exec web python manage.py migrate

.PHONY: compose-super
compose-super: ## 컨테이너 안에서 슈퍼유저 생성
	docker compose exec web python manage.py createsuperuser

.PHONY: compose-down
compose-down: ## docker-compose 종료
	docker compose down
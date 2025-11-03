SHELL := /bin/sh

# ----- 공통 변수 -----
DEV_ENV := envs/.env.dev
PROD_ENV := envs/.env.prod

DJANGO := uv run --env-file $(DEV_ENV) python manage.py
DAPHNE := uv run --env-file $(DEV_ENV) daphne -b 0.0.0.0 -p 8000 config.asgi:application

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

# ---- 도커(개발) ----
.PHONY: compose-up-dev
compose-up-dev: ## docker-compose-dev로 서비스 기동(개발)
	docker compose --env-file .env.dev -f docker-compose.yml -f docker-compose.dev.yml up -d --build

.PHONY: compose-logs-dev
compose-logs-dev: ## docker-compose-dev 로그 보기
	docker compose --env-file $(DEV_ENV) -f docker-compose.yml -f docker-compose.dev.yml logs -f

.PHONY: compose-migrate-dev
compose-migrate-dev: ## dev 컨테이너 안에서 마이그레이션
	docker compose --env-file $(DEV_ENV) -f docker-compose.yml -f docker-compose.dev.yml exec web python manage.py migrate

.PHONY: compose-super-dev
compose-super-dev: ## dev 컨테이너 안에서 슈퍼유저 생성
	docker compose --env-file $(DEV_ENV) -f docker-compose.yml -f docker-compose.dev.yml exec web python manage.py createsuperuser

.PHONY: compose-down-dev
compose-down-dev: ## docker-compose-dev 종료
	docker compose --env-file $(DEV_ENV) -f docker-compose.yml -f docker-compose.dev.yml down


# ----- 도커(스테이징/운영) -----
.PHONY: compose-up-prod
compose-up-prod: ## docker-compose-prod로 서비스 기동(운영)
	docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml up -d --build

.PHONY: compose-logs-prod
compose-logs-prod: ## docker-compose-prod 로그 보기
	docker compose --env-file $(PROD_ENV) -f docker-compose.yml -f docker-compose.prod.yml logs -f

.PHONY: compose-migrate-prod
compose-migrate-prod: ## prod 컨테이너 안에서 마이그레이션
	docker compose --env-file $(PROD_ENV) -f docker-compose.yml -f docker-compose.prod.yml exec web python manage.py migrate

.PHONY: compose-super-prod
compose-super-prod: ## prod 컨테이너 안에서 슈퍼유저 생성
	docker compose --env-file $(PROD_ENV) -f docker-compose.yml -f docker-compose.prod.yml exec web python manage.py createsuperuser

.PHONY: compose-down-prod
compose-down-prod: ## docker-compose-prod 종료
	docker compose --env-file $(PROD_ENV) -f docker-compose.yml -f docker-compose.prod.yml down
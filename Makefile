.PHONY: up down build logs shell-api shell-db migrate seed reset-db lint fmt help

# ── Docker ──────────────────────────────────────────────────────────────────
up:
	docker compose up --build

up-d:
	docker compose up --build -d

down:
	docker compose down

down-v:
	docker compose down -v

build:
	docker compose build

logs:
	docker compose logs -f

logs-api:
	docker compose logs -f api

logs-worker:
	docker compose logs -f worker

# ── Database ─────────────────────────────────────────────────────────────────
migrate:
	docker compose exec api bash -c "cd /app/packages/common && alembic upgrade head"

migrate-down:
	docker compose exec api bash -c "cd /app/packages/common && alembic downgrade -1"

migrate-history:
	docker compose exec api bash -c "cd /app/packages/common && alembic history"

seed:
	docker compose exec api python -m common.seed

reset-db: down-v up-d

shell-db:
	docker compose exec postgres psql -U equitie -d equitie

shell-api:
	docker compose exec api bash

shell-worker:
	docker compose exec worker bash

# ── Local dev (without Docker) ────────────────────────────────────────────────
install:
	uv sync --all-packages

migrate-local:
	cd packages/common && uv run alembic upgrade head

seed-local:
	uv run python -m common.seed

api-local:
	uv run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

worker-local:
	uv run celery -A api.celery_app worker --loglevel=info

# ── Helpers ───────────────────────────────────────────────────────────────────
help:
	@echo "make up          - Build & start all services (foreground)"
	@echo "make up-d        - Build & start all services (detached)"
	@echo "make down        - Stop all services"
	@echo "make down-v      - Stop and remove volumes"
	@echo "make logs        - Tail all logs"
	@echo "make migrate     - Run Alembic migrations inside api container"
	@echo "make seed        - Re-run seed inside api container"
	@echo "make reset-db    - Tear down volumes and restart fresh"
	@echo "make shell-db    - psql session"
	@echo "make shell-api   - bash session in api container"
	@echo "make install     - Install all packages locally with uv"

.PHONY: up down build logs shell-api shell-db migrate seed reset-db lint fmt help \
        test-tools test-tools-k test-tools-q \
        test-eval test-eval-k \
        test-routing test-routing-k \
        test-scope test-scope-k \
        test-persona test-persona-k \
        test-all

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

# ── Tests ─────────────────────────────────────────────────────────────────────
# Prerequisites: `make up-d` (Docker must be running for the database)
#                `make install` (uv venv must have dev dependencies)
#
# Layer 1 — tool unit tests (fast, free, no LLM)
# Layer 2 — fidelity evals   (slow, ~$0.03/case, require ANTHROPIC_API_KEY in .env)

# Layer 1: all 26 edge-case tests, LLM excluded
test-tools:
	DATABASE_URL=postgresql://equitie:equitie@localhost:5432/equitie \
		uv run pytest packages/ai/tests/ -v -m "not eval"

test-tools-q:
	DATABASE_URL=postgresql://equitie:equitie@localhost:5432/equitie \
		uv run pytest packages/ai/tests/ -q -m "not eval"

# Run a single Layer 1 test by keyword: make test-tools-k k=down_round
test-tools-k:
	DATABASE_URL=postgresql://equitie:equitie@localhost:5432/equitie \
		uv run pytest packages/ai/tests/ -v -m "not eval" -k "$(k)"

# Layer 2: number fidelity evals (calls live Claude API — costs money)
# Loads .env so ANTHROPIC_API_KEY is available; DATABASE_URL overrides the Docker value
test-eval:
	bash -c 'set -a; [ -f .env ] && . ./.env; set +a; \
		DATABASE_URL=postgresql://equitie:equitie@localhost:5432/equitie \
		uv run pytest packages/ai/tests/test_number_fidelity.py -v'

# Run a single fidelity eval by keyword: make test-eval-k k=down_round
test-eval-k:
	bash -c 'set -a; [ -f .env ] && . ./.env; set +a; \
		DATABASE_URL=postgresql://equitie:equitie@localhost:5432/equitie \
		uv run pytest packages/ai/tests/test_number_fidelity.py -v -k "$(k)"'

# Layer 3: tool routing golden set (calls live Claude API — costs money)
test-routing:
	bash -c 'set -a; [ -f .env ] && . ./.env; set +a; \
		DATABASE_URL=postgresql://equitie:equitie@localhost:5432/equitie \
		uv run pytest packages/ai/tests/test_tool_routing.py -v'

# Run a single routing case by ID keyword: make test-routing-k k=portfolio_summary
test-routing-k:
	bash -c 'set -a; [ -f .env ] && . ./.env; set +a; \
		DATABASE_URL=postgresql://equitie:equitie@localhost:5432/equitie \
		uv run pytest packages/ai/tests/test_tool_routing.py -v -k "$(k)"'

# Layer 4: scope isolation (3 fast DB tests + 4 eval LLM tests)
test-scope:
	bash -c 'set -a; [ -f .env ] && . ./.env; set +a; \
		DATABASE_URL=postgresql://equitie:equitie@localhost:5432/equitie \
		uv run pytest packages/ai/tests/test_scope_isolation.py -v'

# Run a single scope test by keyword: make test-scope-k k=prompt_injection
test-scope-k:
	bash -c 'set -a; [ -f .env ] && . ./.env; set +a; \
		DATABASE_URL=postgresql://equitie:equitie@localhost:5432/equitie \
		uv run pytest packages/ai/tests/test_scope_isolation.py -v -k "$(k)"'

# Layer 5: personalisation compliance (2 fast DB tests + 4 eval LLM-as-judge tests)
test-persona:
	bash -c 'set -a; [ -f .env ] && . ./.env; set +a; \
		DATABASE_URL=postgresql://equitie:equitie@localhost:5432/equitie \
		uv run pytest packages/ai/tests/test_personalisation.py -v'

# Run a single personalisation test by keyword: make test-persona-k k=contrast
test-persona-k:
	bash -c 'set -a; [ -f .env ] && . ./.env; set +a; \
		DATABASE_URL=postgresql://equitie:equitie@localhost:5432/equitie \
		uv run pytest packages/ai/tests/test_personalisation.py -v -k "$(k)"'

# All layers combined
test-all:
	bash -c 'set -a; [ -f .env ] && . ./.env; set +a; \
		DATABASE_URL=postgresql://equitie:equitie@localhost:5432/equitie \
		uv run pytest packages/ai/tests/ -v'

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
	@echo ""
	@echo "make test-tools              - Layer 1: 26 tool edge-case tests (fast, free)"
	@echo "make test-tools-q            - Layer 1: quiet output"
	@echo "make test-tools-k k=<kw>     - Layer 1: run tests matching keyword"
	@echo "make test-eval               - Layer 2: number fidelity evals (slow, calls Claude API)"
	@echo "make test-eval-k k=<kw>      - Layer 2: run single fidelity case by keyword"
	@echo "make test-routing            - Layer 3: tool routing golden set (calls Claude API)"
	@echo "make test-routing-k k=<id>   - Layer 3: run single routing case by ID keyword"
	@echo "make test-scope              - Layer 4: scope isolation (fast DB + eval LLM)"
	@echo "make test-scope-k k=<kw>     - Layer 4: run single scope test by keyword"
	@echo "make test-persona            - Layer 5: personalisation compliance (LLM-as-judge)"
	@echo "make test-persona-k k=<kw>   - Layer 5: run single personalisation test by keyword"
	@echo "make test-all                - All layers combined"

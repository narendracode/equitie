# EquiTie — CLAUDE.md

## What this project is

EquiTie is a case-study investor platform. It models a simplified SPV investment workflow: investors
commit to deals (one deal per company-round), and the platform tracks allocations, capital calls,
fees, valuations, distributions, and account statements. The centrepiece being built is a
**conversational AI assistant** that answers an investor's questions about their own portfolio,
personalised to their profile.

All portfolio data is synthetic. Report date is **2026-06-25** (treat as "today").

---

## Repo layout

```
EquiTie/
├── packages/
│   ├── common/       SQLAlchemy models, Alembic migrations, seed script
│   ├── ai/           LangGraph agent, tools, personalisation logic  (being built)
│   └── api/          FastAPI app, routers, Celery tasks
├── frontend/         Next.js 14 + Tailwind CSS
├── data/             Seed CSVs (read-only — never modify)
├── docker-compose.yml
├── Makefile
├── system_design.md  Source of truth for all architectural decisions
└── CLAUDE.md         This file
```

Package dependency: `api → common`, `api → ai`, `ai → common`.

---

## Running the project

```bash
make up          # docker compose up --build (full stack)
make up-d        # same, detached
make down        # stop containers
make down-v      # stop and delete volumes (full reset)
make logs-api    # tail API logs
make shell-db    # psql into postgres
make shell-api   # bash into api container
```

Services once running:
- API + Swagger: http://localhost:8000/docs
- Frontend:      http://localhost:3000
- Postgres:      localhost:5432  (user: equitie / pass: equitie / db: equitie)
- Redis:         localhost:6379

Startup sequence (automatic — no manual steps):
1. Postgres becomes healthy
2. API entrypoint runs `alembic upgrade head` then `python -m common.seed` then starts uvicorn
3. Celery worker starts
4. Frontend builds and starts

---

## Package manager

**UV workspaces.** Root `pyproject.toml` declares `members = ["packages/*"]`.
Each package has its own `pyproject.toml`. Inter-package deps use `[tool.uv.sources] pkg = { workspace = true }`.

```bash
uv sync --all-packages        # install everything locally
uv run python -m common.seed  # run a module from any workspace package
```

---

## Database

PostgreSQL 16 with pgvector extension (available, not used yet).

### Existing tables (DO NOT modify schema)

| Table | PK | Key relationships |
|---|---|---|
| `portfolio_companies` | company_id | parent of deals |
| `deals` | deal_id | FK → portfolio_companies; carries std fee schedule |
| `valuations` | valuation_id | FK → deals; time series of marks |
| `investors` | investor_id | has age, tech_savviness, reporting_currency |
| `allocations` | allocation_id | FK → deals + investors; stores effective fee rates |
| `capital_calls` | call_id | FK → allocations |
| `fees` | fee_id | FK → allocations; fee_rate_pct nullable for flat admin fees |
| `distributions` | distribution_id | FK → allocations |
| `statement_lines` | line_id | FK → investors + deals |
| `fx_rates` | currency | USD/GBP/EUR/AED → USD as of 2026-06-25 |

### Migrations

Alembic config lives in `packages/common/alembic.ini`.
Migration files live in `packages/common/alembic/versions/`.

```bash
# inside the api container (or locally with uv run):
cd packages/common && alembic upgrade head
cd packages/common && alembic revision --autogenerate -m "description"
cd packages/common && alembic downgrade -1
```

New migrations go in `packages/common/alembic/versions/` using the next sequence number
(e.g., `0002_chat_tables.py`). The `env.py` reads `DATABASE_URL` from the environment.

---

## AI assistant architecture (system_design.md is the full reference)

### Core principle
LLM does language. Python does maths. The LLM never generates SQL, never does arithmetic,
never invents numbers. Every figure in a response comes from a pre-built tool function.

### Agent: LangGraph ReAct
- Graph: `build_context → agent ⇄ tools → stream_response`
- State holds: `investor_id` (locked), `investor_profile`, `personalization_mode`, `messages`
- `investor_id` is injected into every tool call from state — the LLM never controls it

### Tools (packages/ai/src/ai/tools/)
Ten deterministic Python functions. Each accepts `investor_id` as a fixed param.
All return structured dicts with amounts in both deal currency and reporting currency.

| Tool | Purpose |
|---|---|
| `get_portfolio_summary` | All positions, total committed/contributed, MOIC, DPI, RVPI |
| `get_position_detail(company)` | Single company across all rounds — cost basis, current value, MOIC |
| `get_upcoming_obligations` | Upcoming + overdue capital calls and fees |
| `get_distributions(company?)` | Distributions received — gross, carry withheld, net |
| `get_fee_detail(deal/company)` | Deal std schedule vs investor's effective rates |
| `get_valuation_history(company)` | Full mark time series |
| `get_account_statement(dates?)` | Signed cashflow ledger |
| `get_fx_rates` | Current FX rates |
| `search_company(name)` | Disambiguate company names |
| `get_investor_profile` | Investor profile fields |

### Personalisation
Scoring at session start (`tech_savviness` + `age` + `deal_count`) → mode: `simplified / standard / expert`.
Mode drives the system prompt tone section. Numbers are always identical regardless of mode.

### Streaming
FastAPI SSE endpoint → `graph.astream_events()` → Anthropic streaming.
Event types: `token`, `tool_start`, `tool_end`, `done`.

### New tables needed
`chat_sessions` (session_id, investor_id, created_at, last_active)
`chat_messages` (message_id, session_id, role, content, tool_name, created_at)
V1 prototype may use LangGraph `MemorySaver` (in-memory) instead.

---

## Key data edge cases (tools must handle these, not the LLM)

- **Multi-round companies** — Forgecraft has Seed + Series A + Series B; always group by company_id and label per round
- **Per-investor share price discount** — read `effective_share_price` and `units` from allocation, not from deal
- **Multi-currency** — convert via USD pivot: `amount × (deal_fx.to_usd / reporting_fx.to_usd)`
- **Partial contributions** — `contributed_pct < 100` on DEAL014/DEAL019; show committed vs contributed separately
- **Pending allocation** — Grace Okafor has allocation_status = Pending, contributed = 0
- **Zero holdings** — Henrik Sorensen and Lara Greco have no allocations
- **Exited deal** — Helianthe Energy: current value = 0, distributions exist; MOIC uses distributions only
- **Written-off deal** — Yappio: current value = 0, multiple = 0
- **Down round** — Qubrium Series B: latest mark < entry price
- **Partial secondary** — Tallybook: 30% realised, 70% still live; current_value uses `(1 - 0.3) × units × latest_price`
- **Overdue fees** — flag with warning in `get_upcoming_obligations`
- **Similar names** — Northpeak Analytics ≠ Northpeak Health; `search_company` must return both
- **Admin fee currency** — always USD even on GBP/EUR/AED deals; convert separately

---

## Coding conventions

- **Python 3.12+** — use `X | Y` union types, not `Optional[X]`
- **SQLAlchemy 2.0 style** — `Mapped[type]` + `mapped_column()`; no legacy `Column()`
- **No raw SQL** — use ORM queries in tools; SQL belongs to the developer, not the LLM
- **Pydantic v2** — `model_config = SettingsConfigDict(...)` not inner `class Config`
- **No comments explaining what code does** — only add a comment when the WHY is non-obvious
- **Tool return type** — always a plain `dict`; never raise exceptions to the LLM (return `{"error": "..."}`)
- **FX conversion** — always return both original currency amount and reporting currency amount

---

## Git workflow

**Never commit automatically.** All commits are done manually by the developer after review.
Make file changes freely; do not run `git add` or `git commit` unless explicitly asked.

---

## Environment variables

| Variable | Default (Docker) | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql://equitie:equitie@postgres:5432/equitie` | SQLAlchemy + Alembic |
| `REDIS_URL` | `redis://redis:6379/0` | Celery broker |
| `ANTHROPIC_API_KEY` | — | Required for AI features |
| `DATA_DIR` | `/app/data` | Path to seed CSVs |
| `APP_ENV` | `development` | Environment flag |

Copy `.env.example` to `.env` for local development outside Docker.

# Running EquiTie

This document covers everything needed to get the project running from scratch, operate it day-to-day, and do local development outside Docker.

---

## Prerequisites

| Tool | Minimum version | Install |
|---|---|---|
| Docker Desktop | 24+ | https://docs.docker.com/get-docker/ |
| Docker Compose | v2 (bundled with Docker Desktop) | — |
| `make` | any | macOS: `xcode-select --install` · Linux: `apt install make` |
| `uv` | 0.4+ (local dev only) | `curl -Ls https://astral.sh/uv/install.sh \| sh` |

---

## 1. Environment variables

Copy the example file and fill in your API keys:

```bash
cp .env.example .env
```

Open `.env` and set the following — everything else has working defaults:

```
# Required for the AI assistant
ANTHROPIC_API_KEY=sk-ant-api03-...

# Required for LangSmith tracing and cost tracking
LANGSMITH_API_KEY=lsv2_pt_...
LANGSMITH_PROJECT=equitie            # any project name you like
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
```

Everything else in `.env.example` (Postgres, Redis, database URL) already has correct defaults for the Docker setup and does not need to be changed.

---

## 2. Start the full stack

```bash
make up-d
```

This single command:
1. Builds all four Docker images (Postgres, Redis, API + worker, Next.js frontend)
2. Starts all containers in the correct order
3. Runs Alembic migrations (`alembic upgrade head`) automatically inside the API container
4. Seeds the database with synthetic portfolio data (112 investors, 21 deals, 16 companies)
5. Starts the FastAPI server on port 8000
6. Starts the Celery worker
7. Builds and starts the Next.js frontend on port 3000

First run takes 2–4 minutes (Docker image build + `npm install` + `next build`). Subsequent starts are fast because Docker caches the layers.

Once running:

| Service | URL |
|---|---|
| **Frontend (chat UI)** | http://localhost:3000 |
| **API + Swagger** | http://localhost:8000/docs |
| **Postgres** | `localhost:5432` — user: `equitie` / pass: `equitie` / db: `equitie` |
| **Redis** | `localhost:6379` |
| **LangSmith traces** | https://smith.langchain.com (your project) |

---

## 3. Using the chat

1. Open http://localhost:3000
2. Select an investor from the dropdown (112 available, e.g. **Idris Olawale**)
3. Click **Start Chat →**
4. Ask questions about the portfolio — example prompts are shown on the chat screen

The assistant uses Claude (claude-sonnet-4-6) with thinking mode enabled. A collapsible **"See reasoning"** panel appears above each answer showing Claude's step-by-step reasoning.

---

## 4. Day-to-day commands

```bash
# Start (detached)
make up-d

# Stop
make down

# Stop and delete all data (full reset)
make down-v

# View logs
make logs          # all services
make logs-api      # API only

# Open a shell
make shell-api     # bash inside the API container
make shell-db      # psql session in Postgres

# Re-run seed (safe — uses ON CONFLICT DO NOTHING)
make seed

# Run a new Alembic migration
make migrate
```

---

## 5. Stopping and restarting

```bash
# Restart without losing data
make down && make up-d

# Full reset — deletes the Postgres volume, re-seeds from CSVs
make down-v && make up-d
```

---

## 6. API reference

All endpoints are documented at http://localhost:8000/docs (Swagger UI).

Key chat endpoints:

```
GET  /chat/investors                   List all investors (for the dropdown)
POST /chat/sessions                    Create a session, lock investor_id
GET  /chat/{session_id}/stream         SSE stream: ask a question, receive events
GET  /chat/{session_id}/messages       Full message history for a session
```

SSE event types streamed from `/chat/{session_id}/stream?message=...`:

```json
{"type": "thinking_delta", "content": "..."}   ← reasoning chunk (collapsible panel)
{"type": "token",          "content": "..."}   ← answer text chunk
{"type": "tool_start",     "tool": "...", "label": "Fetching your positions…"}
{"type": "tool_end",       "tool": "..."}
{"type": "done"}
```

---

## 7. Local development (without Docker)

Use this when you need fast iteration on backend code without a full Docker rebuild.

### Backend

```bash
# Install all Python packages into a local virtual environment
uv sync --all-packages

# Start Postgres and Redis via Docker (just the infrastructure)
docker compose up -d postgres redis

# Set environment variables (uses the same .env file)
export $(grep -v '^#' .env | xargs)

# Run migrations
cd packages/common && uv run alembic upgrade head && cd ../..

# Seed the database
uv run python -m common.seed

# Start the API with hot-reload
uv run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# In a separate terminal — start the Celery worker
uv run celery -A api.celery_app worker --loglevel=info
```

### Frontend

```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

The frontend dev server starts on http://localhost:3000 with hot-reload.

---

## 8. Running tool tests

The test suite covers all 13 documented edge cases (zero holdings, pending allocations,
multi-round companies, down rounds, write-offs, exits, partial secondaries, FX conversion,
overdue fees, company disambiguation, admin fee currency, and more). Tests hit the live
seeded database directly — no mocking.

### Prerequisites

```bash
make up-d       # Docker must be running (tests need the database)
make install    # install local Python environment including pytest
```

### Commands

```bash
# Run all 26 tests with full output
make test-tools

# Run with pass/fail summary only (quiet mode)
make test-tools-q

# Run a specific edge case by keyword
make test-tools-k k=down_round
make test-tools-k k=pending
make test-tools-k k=partial_secondary
make test-tools-k k=admin_fee
make test-tools-k k=zero_holdings
make test-tools-k k=disambiguation
```

### Available keyword filters

| Keyword | Tests matched |
|---|---|
| `zero_holdings` | Zero-holdings investors (Henrik, Lara) |
| `pending` | Pending/unfunded allocation (Grace Okafor) |
| `multi_round` | Multi-round Forgecraft position (INV001) |
| `share_price` | Per-investor effective share price discount |
| `multi_currency` or `fx_conversion` | FX conversion to reporting currency |
| `partial_contribution` | Partially funded deal (DEAL014) |
| `exited` | Exited deal — MOIC from distributions only |
| `written_off` | Written-off deal (Yappio) |
| `down_round` | Down-round valuation (Qubrium Series B) |
| `partial_secondary` | Partial secondary sale (Tallybook 30%) |
| `overdue` | Overdue fee flagging |
| `disambiguation` or `northpeak` | Similar company name disambiguation |
| `admin_fee` | Admin fee always stored in USD on non-USD deals |
| `error` or `unknown_investor` | Error handling for invalid inputs |

### Test file locations

```
packages/ai/tests/
├── conftest.py           # session-scoped DB fixture
└── test_edge_cases.py    # 26 tests covering all 13 edge cases
```

---

## 9. Adding a database migration

```bash
# Inside the api container
make shell-api
cd /app/packages/common
alembic revision --autogenerate -m "description of change"
alembic upgrade head
```

Migration files are created in `packages/common/alembic/versions/` using the next sequence number (e.g. `0003_...py`). Commit them alongside the model changes.

---

## 9. Troubleshooting

**API fails to start — "alembic migration error"**
The migration error on a second `docker compose up --build` is benign if the tables already exist. Check `alembic_version` table: if it shows the latest revision, the tables are fine and the API will start normally.

```bash
make shell-db
SELECT * FROM alembic_version;
```

**Frontend shows "Could not load investors"**
The API is still starting up. Wait a few seconds and refresh. You can check API status at http://localhost:8000/health.

**Chat shows "Connection error"**
`ANTHROPIC_API_KEY` is not set or is invalid. Check your `.env` file and restart: `make down && make up-d`.

**LangSmith cost stays NULL in `agent_runs`**
`LANGSMITH_API_KEY` or `LANGSMITH_TRACING=true` is missing from `.env`. The background cost fetch runs 8 seconds after each stream completes — check API logs with `make logs-api` for any `LangSmith cost fetch failed` warnings.

**Full reset**
If the database is in an unknown state, a full reset will rebuild everything from the seed CSVs:

```bash
make down-v && make up-d
```

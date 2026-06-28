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

## 8. Running tests

EquiTie has two test layers:

| Layer | What it tests | Speed | Cost |
|---|---|---|---|
| **Layer 1 — tool unit tests** | 26 edge-case tests, all 13 documented edge cases, no LLM | ~1 s | Free |
| **Layer 2 — number fidelity evals** | 6 end-to-end tests: every stated figure traced back to tool output | ~2.5 min | ~$0.20 |
| **Layer 3 — tool routing** | 20 golden-set questions, one per tool/scenario — checks the right tool was called | ~6 min | ~$0.60 |
| **Layer 4 — scope isolation** | 3 fast DB tests + 4 eval tests: no investor can ever see another's data | 1 s + ~1 min | ~$0.12 |

### Prerequisites

```bash
make up-d       # Docker must be running (tests need the database)
make install    # install local Python environment including pytest
```

For Layer 2, also ensure `ANTHROPIC_API_KEY` is set in your `.env` file.

### Layer 1 — Tool unit tests

```bash
# Run all 26 tests with full output
make test-tools

# Run with pass/fail summary only (quiet mode)
make test-tools-q

# Run a specific edge case by keyword
make test-tools-k k=down_round
make test-tools-k k=pending
make test-tools-k k=partial_secondary
```

#### Available Layer 1 keyword filters

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

### Layer 2 — Number fidelity evals

These call the live Claude API. Each test invokes the full agent end-to-end, captures all tool outputs as ground truth, then checks that every financial figure in the LLM's response is traceable back to a tool — no invented numbers allowed.

```bash
# Run all 6 fidelity cases (~2.5 minutes, costs ~$0.20)
make test-eval

# Run a single case by keyword
make test-eval-k k=down_round
make test-eval-k k=exited
make test-eval-k k=partial_secondary
make test-eval-k k=written_off
make test-eval-k k=portfolio_moic
make test-eval-k k=upcoming_obligations
```

#### What the fidelity check does

The evaluator extracts all numbers from the LLM response and checks each one:
1. **Directly in tool output** — exact match within ±2% rounding tolerance
2. **Arithmetic derivation** — sum, difference, or fractional product of tool-output values (e.g. `paper_loss = cost_basis − current_value`, `remaining_units = units × (1 − realised_fraction)`)

Numbers flagged as "hallucinated" are figures that can't be traced back to any tool output through either path.

#### Known limitation

The LLM occasionally computes holding periods in fractional years (e.g. "2.75 years") which is temporal arithmetic not in any tool output. If `test_fidelity_exited_deal` fails with only a small decimal (< 5) as the hallucinated value, inspect the failure message — it likely shows a "X years Y months" phrase rather than a wrong financial figure.

### Layer 3 — Tool routing

These verify that the agent calls the right tool(s) for each category of question. The golden set has 20 questions, one per routing path, covering all 10 tools. A case passes when every tool in `required_tools` appears anywhere in the agent's call trace — extra tool calls are allowed.

```bash
# Run all 20 routing cases (~6 minutes, costs ~$0.60)
make test-routing

# Run a single case by ID keyword
make test-routing-k k=portfolio_summary_overview
make test-routing-k k=search_disambiguation
make test-routing-k k=fee_detail_company
make test-routing-k k=valuation_history_yappio
make test-routing-k k=account_statement_filtered
```

#### Routing golden set

| Case ID | Investor | Required tool |
|---|---|---|
| `portfolio_summary_overview` | INV001 | `portfolio_summary_tool` |
| `portfolio_summary_totals` | INV001 | `portfolio_summary_tool` |
| `position_detail_multi_round` | INV001 | `position_detail_tool` |
| `position_detail_written_off` | INV010 | `position_detail_tool` |
| `position_detail_exited` | INV011 | `position_detail_tool` |
| `position_detail_down_round` | INV004 | `position_detail_tool` |
| `position_detail_partial_secondary` | INV013 | `position_detail_tool` |
| `search_disambiguation` | INV001 | `search_company_tool` |
| `obligations_upcoming` | INV001 | `upcoming_obligations_tool` |
| `obligations_overdue` | INV001 | `upcoming_obligations_tool` |
| `distributions_all` | INV001 | `distributions_tool` |
| `distributions_company` | INV011 | `distributions_tool` |
| `fee_detail_overview` | INV001 | `fee_detail_tool` |
| `fee_detail_company` | INV001 | `fee_detail_tool` |
| `valuation_history_yappio` | INV010 | `valuation_history_tool` |
| `valuation_history_trend` | INV004 | `valuation_history_tool` |
| `account_statement_full` | INV001 | `account_statement_tool` |
| `account_statement_filtered` | INV001 | `account_statement_tool` |
| `fx_rates` | INV001 | `fx_rates_tool` |
| `investor_profile` | INV001 | `investor_profile_tool` |

### Layer 4 — Scope isolation

These verify that no investor session can ever see another investor's financial data. Three architectural properties are checked: tools return investor-specific data, `investor_id` is absent from every tool schema (the LLM can't override it), and adversarial prompts don't produce data from other investors.

The 3 fast tests run as part of `make test-tools`. The 4 eval tests require the LLM.

```bash
# Run all 8 scope tests (3 fast + 4 eval, ~1 minute)
make test-scope

# Run a single scope test by keyword
make test-scope-k k=prompt_injection
make test-scope-k k=cross_investor
make test-scope-k k=named_investor
make test-scope-k k=tool_trace
make test-scope-k k="not eval"    # fast tests only
```

#### What each test verifies

| Test | Type | What it checks |
|---|---|---|
| `test_scope_tools_return_investor_specific_data` | Fast | Same tool → different results for different investor IDs |
| `test_scope_investor_id_not_in_tool_schemas` | Fast | `investor_id` absent from every tool's LLM-visible schema |
| `test_scope_unowned_position_returns_empty` | Fast | Asking about a position you don't hold returns empty, not another investor's data |
| `test_scope_tool_trace_matches_authenticated_investor` | Eval | Tool output in trace exactly matches direct call for same investor_id |
| `test_scope_cross_investor_id_request_blocked` | Eval | Asking for another investor by ID produces no foreign financial figures |
| `test_scope_prompt_injection_blocked` | Eval | Admin-mode injection attempt produces no multi-investor data |
| `test_scope_named_investor_request_blocked` | Eval | Asking by investor name produces no foreign financial figures |
| `test_scope_out_of_scope_position_returns_not_found` | Eval | Investor with zero holdings asking about a deal returns empty, not another's data |

### All layers combined

```bash
make test-all   # runs all 26 + 6 + 20 + 8 tests (~10 minutes)
```

### Test file locations

```
packages/ai/tests/
├── conftest.py                 # session-scoped DB fixture
├── eval_utils.py               # shared helpers: number fidelity, tool name extraction
├── test_edge_cases.py          # Layer 1: 26 tests covering all 13 edge cases
├── test_number_fidelity.py     # Layer 2: 6 end-to-end fidelity evals
├── test_tool_routing.py        # Layer 3: 20 routing golden-set cases
└── test_scope_isolation.py     # Layer 4: 3 fast + 4 eval scope isolation tests
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

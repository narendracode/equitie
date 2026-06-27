# EquiTie — System Design

> Report date: 2026-06-25 (treat as "today" for upcoming/current figures)

---

## Overview

EquiTie is an AI-powered investor platform for managing SPV (Special Purpose Vehicle) investments. Investors commit to deals, each deal invests in one funding round of a portfolio company, and the platform tracks capital contributions, fees, valuations, distributions and per-investor account statements.

---

## Tech Stack

| Layer | Technology |
|---|---|
| API | Python · FastAPI · SQLAlchemy 2 · Alembic |
| AI | LangChain · LangGraph · Anthropic Claude |
| Task queue | Celery + Redis |
| Database | PostgreSQL 16 + pgvector |
| Frontend | Next.js 14 (App Router) · Tailwind CSS |
| Packaging | UV workspaces (monorepo) |
| Infrastructure | Docker Compose |

---

## Repository Structure

```
EquiTie/
├── packages/
│   ├── common/          # SQLAlchemy models, DB session, Alembic migrations, seed
│   ├── ai/              # LangChain agents, tools, graph definitions
│   └── api/             # FastAPI app, routers, Celery tasks
├── frontend/            # Next.js app
├── data/                # Seed CSV files (synthetic)
├── docker-compose.yml
├── Makefile
└── system_design.md     ← this file
```

### Package dependency graph

```
api ──► common
api ──► ai
ai  ──► common
```

---

## Data Model

### Entity Relationship

```
portfolio_companies (1) ──< deals (1) ──< allocations >── (1) investors
                                 │                 │
                                 ├──< valuations   ├──< capital_calls
                                 │                 ├──< fees
                                 │                 └──< distributions
fx_rates (currency ref)          └──────────────────────< statement_lines >── investors
```

### Tables

| Table | Rows | Notes |
|---|---|---|
| `portfolio_companies` | 16 | One company can span multiple rounds/deals |
| `deals` | 21 | One per company-round SPV; carries standard fee schedule |
| `valuations` | 55 | Time-series marks per deal; latest mark drives current value |
| `investors` | 112 | Includes `age` and `tech_savviness` for AI personalisation |
| `allocations` | 550 | Core fact table; per-investor position in a deal; stores effective fee rates |
| `capital_calls` | 655 | Tranched calls against an allocation |
| `fees` | 1,401 | Per-allocation fee rows (Management / Structuring / Admin) |
| `distributions` | 34 | Exit proceeds and secondary sales, net of performance fee |
| `statement_lines` | 1,390 | Signed per-investor cashflow ledger |
| `fx_rates` | 4 | USD/GBP/EUR/AED → USD rates as of report date |

### Key design decisions

1. **Fee rates live on the allocation, not the deal.** Each allocation stores its own effective `mgmt_fee_pct`, `performance_fee_pct`, `structuring_fee_pct`, `admin_fee_usd` (which may be discounted below the deal's `std_*` equivalents). The `fee_discount` flag marks any allocation where at least one rate was negotiated down.

2. **Multi-currency.** `deal_currency` drives contribution/fee/distribution amounts. `reporting_currency` on the investor drives display. All aggregations must FX-convert via `fx_rates` (convert through USD).

3. **Effective share price per allocation.** `price_discount_pct` gives early-bird / side-letter investors a lower cost basis, driving a different `units` count from the same deal.

4. **Partial contributions.** `deal.contributed_pct < 100` means capital is partially called; `allocation.outstanding_commitment > 0` is the investor's remaining obligation. Two deals currently have outstanding calls.

5. **Derived metrics** (computed at query time, not stored):
   - **Current value** = `units × latest_share_price` minus realised fraction, in deal currency
   - **MOIC** = (current_value + distributions_net) ÷ contributed_amount
   - **DPI** = distributions ÷ contributed; **RVPI** = current_value ÷ contributed
   - **Portfolio total** = Σ current_values converted to investor's `reporting_currency`

---

## API Design

```
GET  /health                         # liveness probe
GET  /investors                      # paginated investor list
GET  /investors/{id}                 # investor detail + portfolio summary
GET  /investors/{id}/allocations     # positions with current values
GET  /investors/{id}/statement       # account statement (signed cashflows)
GET  /deals                          # deal list with latest valuation
GET  /deals/{id}                     # deal detail + all allocations
GET  /portfolio-companies            # company list
GET  /portfolio-companies/{id}       # company detail + all deals
```

---

## AI Layer (planned)

- **Portfolio assistant** — LangGraph agent backed by Claude; answers natural-language questions about an investor's portfolio, fees, upcoming obligations and performance.
- **Tools**: SQL query tool, FX conversion tool, MOIC calculator.
- **Personalisation signals**: `age`, `tech_savviness`, deal count, top sectors.

---

## Startup Sequence (Docker Compose)

```
postgres (healthy)
    └─► api container entrypoint:
            1. alembic upgrade head   (idempotent)
            2. python -m common.seed  (idempotent — ON CONFLICT DO NOTHING)
            3. uvicorn api.main:app
redis (healthy)
    └─► worker container:
            celery -A api.celery_app worker
frontend:
    └─► next start (port 3000)
```

No manual steps required after `docker compose up --build`.

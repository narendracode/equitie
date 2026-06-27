# EquiTie — System Design

> Report date: 2026-06-25 (treat as "today" for upcoming/current figures)

---

## Overview

EquiTie is an AI-powered investor platform for managing SPV investments. Its centrepiece is a
**conversational Investor Assistant** that answers natural-language questions about an investor's
own portfolio — personalised to their profile — while keeping every number provably correct.

---

## Tech Stack

| Layer | Technology |
|---|---|
| API | Python · FastAPI · SQLAlchemy 2 · Alembic |
| AI agent | LangGraph · LangChain · Anthropic Claude (claude-sonnet-4-6) |
| Streaming | FastAPI SSE (Server-Sent Events) · EventSource (browser) |
| Task queue | Celery + Redis |
| Database | PostgreSQL 16 + pgvector (vector extension available; not used in V1) |
| Frontend | Next.js 14 (App Router) · Tailwind CSS |
| Packaging | UV workspaces (monorepo) |
| Infrastructure | Docker Compose |

---

## Repository Structure

```
EquiTie/
├── packages/
│   ├── common/          # SQLAlchemy models, DB session, Alembic migrations, seed
│   ├── ai/              # LangGraph agent, tools, personalization logic
│   └── api/             # FastAPI app, chat routers, Celery tasks
├── frontend/            # Next.js app (investor selector + chat UI)
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

## Data Model (existing — no changes)

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

### Key data design decisions

1. **Fee rates live on the allocation, not the deal.** Each allocation stores effective `mgmt_fee_pct`,
   `performance_fee_pct`, `structuring_fee_pct`, `admin_fee_usd` (may be discounted below `std_*`).
2. **Multi-currency.** `deal_currency` drives amounts. `reporting_currency` on the investor drives
   display. All aggregations FX-convert via `fx_rates` (always go via USD as the pivot).
3. **Effective share price per allocation.** `price_discount_pct` gives different cost bases per investor.
4. **Partial contributions.** `deal.contributed_pct < 100` → outstanding commitment exists.
5. **Derived metrics** (computed in Python tools, never by the LLM):
   - **Current value** = `units × latest_share_price` × (1 − realised_fraction), in deal currency
   - **MOIC** = (current_value + Σ distributions_net) ÷ contributed_amount
   - **DPI** = Σ distributions_net ÷ contributed; **RVPI** = current_value ÷ contributed
   - **Portfolio total** = Σ current_values converted to investor's reporting currency

---

## New Tables Required (V1 — chat persistence)

Two lightweight tables are added to support multi-turn conversation history.
These are the **only** schema additions needed.

```
chat_sessions
  session_id     UUID  PK
  investor_id    VARCHAR  FK → investors
  created_at     TIMESTAMP
  last_active    TIMESTAMP

chat_messages
  message_id     UUID  PK
  session_id     UUID  FK → chat_sessions
  role           VARCHAR  (user | assistant | tool)
  content        TEXT
  tool_name      VARCHAR  nullable (populated for tool messages)
  created_at     TIMESTAMP
```

> For V1 prototype, LangGraph's in-memory `MemorySaver` checkpointer can be used
> (no DB tables needed). Promote to DB-backed storage when persistence across restarts matters.

---

## Investor Assistant — Architecture Design

### Core Principle: LLM does language, Python does maths

The single most important design decision is the **strict separation of concerns**:

| Responsibility | Handled by |
|---|---|
| Routing questions to the right query | LLM (ReAct reasoning) |
| Fetching data from the database | Pre-built Python tool functions |
| Arithmetic (MOIC, DPI, FX conversion, fee sums) | Python inside tools |
| Converting numbers to natural-language prose | LLM |
| Personalisation (tone, depth, jargon) | System prompt + LLM |

The LLM **never** generates SQL, never does arithmetic, and never invents numbers.
Every figure in the response is retrieved or calculated by a tool function and passed to the LLM
as structured JSON. The LLM only decides *which* tool to call and *how* to explain the result.

---

### Is RAG / Vector Search Required?

**No — not for V1, and not for the foreseeable core use case.**

RAG (Retrieval Augmented Generation) solves the problem of finding relevant chunks in a large
unstructured document corpus. Our data is:
- Fully structured in a relational database (PostgreSQL)
- Small and precisely queryable (< 5 000 rows per investor)
- Well-described by a compact schema summary that fits in a system prompt

Using a vector store + embeddings for this data would add complexity (embedding pipeline,
pgvector tables, chunking strategy) with no accuracy benefit — and likely *worse* results,
since semantic similarity retrieval over financial figures is unreliable.

**When vector search WOULD be useful (future):**
- If company descriptions, investment theses, or deal notes were stored as free text
- If the assistant needed to answer questions like "which of my deals are in climate tech?" by
  scanning qualitative data that is not cleanly tagged
- If a knowledge base of help articles or financial glossary needed semantic search

The `pgvector` extension is already installed in the Docker image and can be activated later
without infrastructure changes. For V1 it is unused.

---

### Agent Architecture — LangGraph ReAct

**Why ReAct (Reason + Act)?**

An investor question often requires several data fetches composed together. For example:

> "What's my overall MOIC?"

This requires:
1. Get all allocations → contributed amounts per deal currency
2. Get latest valuation per deal → current value
3. Get all distributions (net) per deal
4. Get FX rates → convert everything to reporting currency
5. Sum and divide

A **ReAct agent** handles this naturally: it reasons about what is missing, calls the right tools
in sequence (or in parallel where LangGraph supports it), and accumulates context before answering.

A plain chain or simple prompt would require the developer to hard-code this multi-step logic for
every possible question type. ReAct generalises across question complexity.

**Why LangGraph specifically (not LangChain LCEL chain)?**

| Feature | LCEL Chain | LangGraph |
|---|---|---|
| Multi-turn conversation state | Manual | Built-in (state graph) |
| Conditional branching (clarify / answer) | Awkward | Native (edges + conditions) |
| Streaming tokens + tool events | Partial | Full event stream |
| Checkpointing (resume sessions) | No | Yes (MemorySaver / DB) |
| Human-in-the-loop (future) | No | Yes |
| Parallel tool calls | No | Yes (Send API) |

---

### LangGraph Graph — Node Definitions

```
START
  │
  ▼
[build_context]          Loads investor_profile, computes personalization_mode,
  │                      builds dynamic system prompt. Runs once per session start.
  │
  ▼
[agent]  ◄──────────┐    Claude reasons: does it need a tool? Or can it answer?
  │                 │
  ├─ tool calls ──► [tools]   Executes one or more tool functions in parallel.
  │                 │         Returns structured JSON results to agent.
  │                 └─────────┘
  │
  └─ final answer ──► [stream_response] ──► END
                       Streams tokens to SSE endpoint.
```

**State schema:**

```python
class AgentState(TypedDict):
    investor_id: str                  # locked at session creation, never changes
    investor_profile: dict            # name, age, tech_savviness, reporting_currency, etc.
    personalization_mode: str         # "simplified" | "standard" | "expert"
    system_prompt: str                # built once from profile; injected each LLM call
    messages: list[BaseMessage]       # full conversation history (HumanMessage + AIMessage)
```

The `investor_id` is injected into every tool call transparently — the LLM never sees or controls
the investor_id. It is a locked field in state.

---

### Tool Catalogue

Ten deterministic Python functions. Each takes `investor_id` as a fixed parameter (injected from
state, not from the LLM's output). All amounts returned in **both** deal currency and the
investor's reporting currency.

| Tool | What it answers | Key edge cases handled |
|---|---|---|
| `get_portfolio_summary` | All positions: total committed, contributed, current value, distributions, MOIC, DPI, RVPI | Multi-currency aggregation; exited/written-off deals correctly zero'd for current value; partial contributions |
| `get_position_detail(company_name_or_id)` | Single company (all rounds): cost basis, units, current value, MOIC per round + aggregate | Multi-round companies (Forgecraft: Seed/A/B); per-investor effective share price; down rounds; partial exit (Tallybook 30% secondary) |
| `get_upcoming_obligations` | Capital calls (Upcoming) + fees (Upcoming + Overdue) with due dates | Overdue fees flagged separately; amounts in deal and reporting currency |
| `get_distributions(company_name_or_id=None)` | Distributions received — gross, performance fee withheld, net | Fraction of units realised; full exit vs partial secondary; exit value vs mark-to-zero |
| `get_fee_detail(deal_id_or_company)` | Fee structure: deal standard vs investor's effective rates; paid + upcoming | Shows discount where applicable; admin fee always in USD even on non-USD deals |
| `get_valuation_history(company_name_or_id)` | Full mark history: date, share price, multiple vs entry, source | Down rounds; write-offs (multiple = 0); markup rounds; exit marks |
| `get_account_statement(start_date=None, end_date=None)` | Signed cashflow ledger: contributions (−), fees (−), distributions (+) | Ordered by date; net position (how much cash in vs out) |
| `get_fx_rates` | Current FX rates (USD/GBP/EUR/AED) | Used for explicit "what is this in GBP?" questions |
| `search_company(name_query)` | Disambiguate company names → returns matching company_id(s) | Handles "Northpeak" → returns both Northpeak Analytics + Northpeak Health for user to confirm |
| `get_investor_profile` | Investor's own profile fields | For self-referential questions ("am I KYC verified?", "what's my reporting currency?") |

**What tools do NOT do:**
- Generate SQL dynamically
- Accept free-form query strings from the LLM
- Return raw DB rows (they return computed, labelled JSON)

---

### Data Fetching Strategy

Tools use **SQLAlchemy ORM queries** (no raw SQL) against the existing 10 tables.
No new ingestion pipeline. No embeddings. No ETL.

Each tool is a pure Python function:
```
tool_function(investor_id, **params) → dict
```

Calculations happen inside the tool before returning:
- FX conversion: `amount_in_deal_currency × (deal_fx.to_usd / reporting_fx.to_usd)`
- MOIC: `(current_value + net_distributions) / contributed_amount`
- Current value: `units × (1 - realised_fraction) × latest_share_price`
- Net distribution: `gross_amount - performance_fee_amount`

The LLM receives the pre-computed result and only needs to describe it.

---

### Streaming Architecture

```
Browser (Next.js)
│  EventSource → /chat/{session_id}/stream?message=...
│  OR fetch() with ReadableStream
│
FastAPI (api package)
│  POST /chat/sessions                  → create session, return session_id
│  GET  /chat/{session_id}/stream       → SSE endpoint
│       yields: data: {"type":"token","content":"..."}
│               data: {"type":"tool_start","tool":"get_portfolio_summary"}
│               data: {"type":"tool_end","tool":"...","summary":"..."}
│               data: {"type":"done"}
│
LangGraph agent (ai package)
│  graph.astream_events(input, config)
│  yields LangChain event stream:
│    on_chat_model_stream  → token deltas → forwarded to SSE
│    on_tool_start         → tool name → forwarded to SSE ("Looking up your portfolio...")
│    on_tool_end           → tool result (not shown verbatim to user)
│
Anthropic claude-sonnet-4-6
   streaming=True, max_tokens=2048
```

Frontend behaviour:
- Typing indicator shown until first token arrives
- Tool call events show a brief status ("Fetching your positions…") while tool runs
- Text streams in as tokens arrive
- On `done`, message is finalised in the chat history

---

### Personalisation System

**Principle:** Same numbers for everyone. Different depth, tone, and framing.

#### Step 1 — Compute personalization_mode at session start

```
Input signals:
  tech_savviness : Low | Medium | High          (stored on investor)
  age            : integer or null              (stored on investor; null for entities)
  deal_count     : count(allocations)           (derived at session start)
  investor_type  : Individual | Entity          (stored on investor)

Scoring:
  +2  tech_savviness == High
  +1  tech_savviness == Medium
  +1  deal_count >= 5
  +1  age < 50 (where known)
  −1  age >= 65 (where known)

Mode:
  score >= 3  →  "expert"
  score == 2  →  "standard"
  score <= 1  →  "simplified"
```

#### Step 2 — Build personalised system prompt

The system prompt is constructed dynamically from the investor's profile and injected into every
LLM call in the session.

**Fixed section (all investors):**
```
You are the EquiTie Investor Assistant. You help {investor_name} understand their
investment portfolio. Today's date is 2026-06-25.

IMPORTANT RULES:
- You only answer questions about {investor_name}'s own portfolio (investor_id: {id}).
- Every number you state must come from the tool results provided to you. Never invent figures.
- If a tool result is empty (e.g. no distributions), say so clearly.
- Always state which currency amounts are in.
- For multi-round companies, always clarify which round(s) you are describing.
- Reporting currency for this investor is {reporting_currency}.
```

**Personalisation section — "simplified":**
```
Communication style:
- Use plain English. Avoid jargon. If you must use a term like MOIC or carry, 
  explain it in parentheses the first time: "MOIC (how many times their money has grown)".
- Keep answers focused. Lead with the bottom line, then supporting detail.
- Use concrete language: "you have earned £X back" rather than "realised DPI of 1.5×".
- Be warm and reassuring in tone, never condescending.
```

**Personalisation section — "standard":**
```
Communication style:
- Use clear professional language. Define terms that are not everyday vocabulary.
- Structure answers with a headline figure, then a brief breakdown.
- Reference the investor's most active sectors where relevant: {top_sectors}.
```

**Personalisation section — "expert":**
```
Communication style:
- Be concise and data-dense. Assume fluency with MOIC, DPI, RVPI, carry, SPV, SAFE.
- Lead with key metrics. Use tables where multiple positions are compared.
- No need to define standard VC/PE vocabulary.
- Reference portfolio concentration and cross-round positions where relevant.
- The investor holds {deal_count} positions across {sector_summary}.
```

#### Step 3 — Reflective personalisation at response time

Beyond system-prompt tone, the LLM is instructed to:
- Reference the investor's most active sectors in portfolio-level answers
  ("Your heaviest exposure is in Digital Health and Robotics / Automation")
- Adapt framing to what the investor actually holds
  (if they have an exit, lead with realised proceeds; if they have overdue fees, flag them early)
- For multi-round holdings, always show per-round and aggregate views

---

### Handling Tricky Data Cases

These edge cases must be handled by tools, not reasoned about by the LLM:

| Case | Tool handling |
|---|---|
| Same company in multiple rounds | `get_position_detail` groups by `company_id`, returns one row per round + an aggregate. Always labels "Forgecraft Seed", "Forgecraft Series A", etc. |
| Per-investor share-price discount | `effective_share_price` and `units` are read from allocation, not deal |
| Multi-currency | Every tool converts to reporting currency using `fx_rates`. Both amounts always returned (deal currency + reporting currency) |
| Partial contribution (contributed_pct < 100) | `get_portfolio_summary` reports both `committed` and `contributed` separately. Outstanding commitment shown explicitly |
| Pending/unfunded allocation | allocation_status == 'Pending' → contributed = 0; flagged in summary |
| Zero-holding investors (Henrik, Lara) | `get_portfolio_summary` returns empty allocations list; assistant says "You have no active investments yet" |
| Exited deal (Helianthe Energy) | Current value = 0; distributions exist; MOIC = net_distributions ÷ contributed. Tool handles this explicitly |
| Written-off deal (Yappio) | Current value = 0; multiple = 0; MOIC < 1 |
| Down round (Qubrium Series B) | Latest share_price < entry_share_price; multiple_vs_entry < 1. Tool returns both entry price and current mark |
| Partial secondary (Tallybook) | realised_fraction = 0.3 → current value uses (1 − 0.3) × units × latest_price; distribution exists for 30% |
| Overdue fees | fees with status == 'Overdue' flagged with ⚠ in `get_upcoming_obligations` |
| Similar company names | `search_company("Northpeak")` returns both; assistant asks user to confirm before answering |
| Admin fee always in USD | fee.currency == 'USD' even on GBP/EUR/AED deals. Tool handles FX conversion of admin fee separately |

---

### Determinism and Reliability

**Why this design is predictable:**

1. **No LLM-generated SQL.** All queries are written by the developer. The LLM only picks which
   tool to call. A wrong tool call returns an empty result or an error message — it does not corrupt data.

2. **All arithmetic in Python.** MOIC, DPI, FX conversion are computed in tool functions that
   have unit tests. The LLM only formats the output.

3. **Structured tool outputs.** Every tool returns a typed dict with labelled fields.
   The LLM cannot confuse "gross_amount" with "net_amount" because both are explicitly named.

4. **Investor_id locked in state.** The LLM never receives the investor_id as a parameter it can
   change. It is injected from state at every tool call transparently.

5. **Temperature = 0 (or near-zero).** For factual financial responses, Claude is called at
   temperature 0. Personalization affects structure and tone, not numerical output.

6. **Explicit currency labelling.** Tools always return `{"amount": 42000, "currency": "GBP"}`.
   The system prompt instructs the LLM to always state the currency. Ambiguity is eliminated.

7. **Empty-state handling.** Tools return explicit empty states (`{"allocations": [], "message": "no positions found"}`)
   rather than null/None, preventing the LLM from hallucinating data.

---

### API Endpoints (additions to existing)

```
# Session management
POST /chat/sessions
     body: { "investor_id": "INV001" }
     → { "session_id": "uuid", "investor_name": "Idris Olawale" }

# Streaming chat (SSE)
GET  /chat/{session_id}/stream?message=<url-encoded-text>
     → text/event-stream
        data: {"type":"token","content":"Your portfolio..."}
        data: {"type":"tool_start","tool":"get_portfolio_summary","label":"Fetching your positions…"}
        data: {"type":"tool_end","tool":"get_portfolio_summary"}
        data: {"type":"done"}

# Chat history (non-streaming, for reload)
GET  /chat/{session_id}/messages
     → [ { role, content, created_at }, ... ]

# Available investors (for dropdown)
GET  /chat/investors
     → [ { investor_id, investor_name, reporting_currency }, ... ]
```

---

## API Design (full, including prior endpoints)

```
# Health
GET  /health

# Investors (read-only data)
GET  /investors
GET  /investors/{id}
GET  /investors/{id}/allocations
GET  /investors/{id}/statement

# Deals
GET  /deals
GET  /deals/{id}

# Portfolio companies
GET  /portfolio-companies
GET  /portfolio-companies/{id}

# AI Chat (new)
GET  /chat/investors
POST /chat/sessions
GET  /chat/{session_id}/stream        ← SSE, primary endpoint
GET  /chat/{session_id}/messages
```

---

## Frontend Design

```
Page: /  (dashboard)
  └── Investor selector dropdown (populated from GET /chat/investors)
      → On select: POST /chat/sessions → stores session_id in state

Page: /chat  (or right panel on same page)
  ├── Chat message list (streamed)
  │     ├── User messages (right-aligned)
  │     ├── Tool status chips ("Fetching your positions…") while tool runs
  │     └── Assistant messages (left-aligned, streaming)
  ├── Input box + send button
  └── Investor context chip (name + reporting currency, locked for session)
```

Suggested starter prompts shown when chat opens (per investor, based on what they hold):
- "Give me an overview of my portfolio"
- "What are my upcoming obligations?"
- "How has my Forgecraft position performed?"

---

## Startup Sequence (Docker Compose — unchanged)

```
postgres (healthy)
    └─► api container entrypoint:
            1. alembic upgrade head   (idempotent — includes chat_sessions/chat_messages tables)
            2. python -m common.seed  (idempotent — ON CONFLICT DO NOTHING)
            3. uvicorn api.main:app
redis (healthy)
    └─► worker container:
            celery -A api.celery_app worker
frontend:
    └─► next start (port 3000)
```

No manual steps required after `docker compose up --build`.

---

## Decision Log

| Question | Decision | Reason |
|---|---|---|
| RAG / vector search? | No (V1) | Data is structured SQL, not unstructured documents. Tools give exact results; RAG would add noise. pgvector available for V2 if free-text notes are added. |
| Text-to-SQL? | No | LLM-generated SQL is unpredictable for financial calculations. Pre-built tools are correct by construction. |
| Agent type? | LangGraph ReAct | Multi-step data composition; conversation state; streaming; future extensibility (human-in-the-loop, clarification nodes). |
| New DB tables? | Only chat_sessions + chat_messages | All investor/portfolio data is in existing tables. No ETL, no embeddings, no new fact tables. |
| Arithmetic in LLM? | Never | All MOIC / DPI / FX maths is in Python tool functions. LLM only formats prose. |
| Investor_id security | Locked in state | LLM cannot escape the investor's data scope. Injected at every tool call, not passed as LLM parameter. |
| LLM temperature | 0 | Financial facts must be stable. Personalization is in the system prompt, not in stochastic generation. |
| Conversation memory | LangGraph MemorySaver (V1) → DB-backed (V2) | Prototype doesn't need cross-restart persistence. |
| Streaming protocol | Server-Sent Events (SSE) | Simpler than WebSockets for unidirectional server→client streams; native browser EventSource support. |

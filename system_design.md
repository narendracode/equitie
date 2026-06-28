# System Design

---

## Overview

EquiTie is an AI-powered investor platform for managing SPV investments. Its centrepiece is a
**conversational Investor Assistant** that answers natural-language questions about an investor's
own portfolio personalised to their profile while keeping every number provably correct.

The platform models the full SPV investment lifecycle: capital commitments, tranched capital calls,
fee schedules, mark-to-market valuations, distributions, and signed cashflow statements.

---

## Key Decisions at a Glance

| Question | Answer | One-line reason |
|---|---|---|
| RAG / vector search? | **No** | Data is structured SQL — tools give exact results; RAG adds noise over financial figures |
| Text-to-SQL? | **No** | LLM-generated SQL is unpredictable for financial calculations; pre-built tools are correct by construction |
| Agent type? | **LangGraph ReAct** | Portfolio questions require composing multiple fetches; ReAct generalises across complexity |
| New DB tables? | **chat_sessions + chat_messages + agent_runs** | Zero changes to investor/portfolio schema |
| Does the LLM do arithmetic? | **Never** | All MOIC / DPI / FX maths lives in Python tool functions; LLM only formats prose |
| investor_id security | **Locked in graph state** | LLM cannot escape the investor's data scope — injected at every tool call, not passed as LLM param |
| LLM temperature | **0** | Financial facts must be stable; personalisation is in the system prompt, not stochastic generation |
| Conversation memory | **LangGraph MemorySaver + Postgres persistence** | In-process state for live sessions; durable message history in chat_messages for reload and auditability |
| Streaming protocol | **Server-Sent Events (SSE)** | Simpler than WebSockets for unidirectional streams; native browser EventSource |
| LangSmith tracing | **agent_runs table** | Per-run cost + debug trace URL linked to chat_messages for end-to-end observability |
| LLM model | **claude-sonnet-4-6** | Supports adaptive thinking; LLM only routes and narrates — Python tools do all maths; Sonnet cost ($3/$15 per 1M) is proportionate to that lighter role |
| Thinking mode | **Visible streaming** | Users see the assistant's reasoning in a collapsible panel; builds trust in financial decisions |

---

## Tech Stack

| Layer | Technology |
|---|---|
| API | Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic |
| AI agent | LangGraph · LangChain · Anthropic Claude (claude-sonnet-4-6) |
| Streaming | FastAPI SSE (Server-Sent Events) · EventSource (browser) |
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
│   ├── ai/              # LangGraph agent, tools, personalisation logic
│   └── api/             # FastAPI app, chat routers, Celery tasks
├── frontend/            # Next.js app (investor selector + chat UI)
├── data/                # Seed CSV files (synthetic, read-only)
├── docker-compose.yml
├── Makefile
└── system_design.md
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

### Portfolio Tables

| Table | Notes |
|---|---|
| `portfolio_companies` | One company can span multiple rounds/deals |
| `deals` | One per company-round SPV; carries standard fee schedule |
| `valuations` | Time-series marks per deal; latest mark drives current value |
| `investors` | Includes `age` and `tech_savviness` for AI personalisation |
| `allocations` | Core fact table; per-investor position in a deal; stores effective fee rates |
| `capital_calls` | Tranched calls against an allocation |
| `fees` | Per-allocation fee rows (Management / Structuring / Admin) |
| `distributions` | Exit proceeds and secondary sales, net of performance fee |
| `statement_lines` | Signed per-investor cashflow ledger |
| `fx_rates` | USD/GBP/EUR/AED → USD rates as of report date |

### Key data design decisions

1. **Derived metrics** (computed in Python tools, never by the LLM):
   - **Current value** = `units × latest_share_price × (1 − realised_fraction)`, in deal currency
   - **MOIC** = (current_value + Σ distributions_net) ÷ contributed_amount
   - **DPI** = Σ distributions_net ÷ contributed; **RVPI** = current_value ÷ contributed
   - **Portfolio total** = Σ current_values converted to investor's reporting currency

---

## Chat Persistence Schema

Three lightweight tables support conversation history, thinking content, and cost observability.
These are the only schema additions to the existing portfolio tables.

```
chat_sessions
  session_id     UUID  PK
  investor_id    VARCHAR  FK → investors
  created_at     TIMESTAMP
  last_active    TIMESTAMP

chat_messages
  message_id        UUID  PK
  session_id        UUID  FK → chat_sessions
  role              VARCHAR  (user | assistant | tool)
  content           TEXT
  thinking_content  TEXT  nullable  (assistant messages only — persisted thinking summary)
  tool_name         VARCHAR  nullable
  created_at        TIMESTAMP

agent_runs
  run_id               UUID  PK  (= LangSmith run_id from astream_events)
  session_id           UUID  FK → chat_sessions
  user_message_id      UUID  FK → chat_messages
  assistant_message_id UUID  FK → chat_messages  nullable — set on completion
  trace_url            VARCHAR
  model_name           VARCHAR
  prompt_tokens        INTEGER
  completion_tokens    INTEGER  (includes thinking tokens — billed as output on Sonnet 4.6)
  cost_usd             NUMERIC(10,6)
  duration_ms          INTEGER
  status               VARCHAR  (running | completed | error)
  created_at           TIMESTAMP
  completed_at         TIMESTAMP  nullable
```

---

## Investor Assistant — Architecture

### Core Principle: LLM does language, Python does maths

The fundamental design decision is a **strict separation of concerns**:

| Responsibility | Handled by |
|---|---|
| Routing questions to the right query | LLM (ReAct reasoning) |
| Fetching data from the database | Pre-built Python tool functions |
| Arithmetic (MOIC, DPI, FX conversion, fee sums) | Python inside tools |
| Converting numbers to natural-language prose | LLM |
| Personalisation (tone, depth, jargon) | System prompt + LLM |

The LLM never generates SQL, never does arithmetic, and never invents numbers.
Every figure in a response is retrieved or calculated by a tool function and passed to the LLM
as structured JSON. The LLM only decides *which* tool to call and *how* to explain the result.

---

### Why Not RAG or Text-to-SQL?

**RAG** solves the problem of finding relevant chunks in a large unstructured document corpus.
The portfolio data is fully structured in a relational database, small and precisely queryable
(< 5,000 rows per investor), and well-described by a compact schema summary that fits in a
system prompt. Using a vector store over financial figures would produce less accurate results
than a deterministic ORM query, not more.

**Text-to-SQL** is unsuitable because LLM-generated SQL is non-deterministic over financial
calculations. Pre-built tool functions are correct by construction: they handle edge cases
(partial secondaries, down rounds, write-offs, multi-currency aggregation) explicitly and
are testable independently of the LLM.

---

### Agent Architecture — LangGraph ReAct

An investor question typically requires several data fetches composed together. For example,
computing an overall MOIC requires: allocations (contributed amounts), latest valuations
(current value per deal), distributions (realised proceeds), and FX rates (to convert to
reporting currency). A ReAct agent handles this naturally — it reasons about what is missing,
calls the right tools in sequence or in parallel, and accumulates context before answering.
A fixed chain would require hard-coding this multi-step logic for every possible question type.

**Why LangGraph over LCEL chains:**

| Feature | LCEL Chain | LangGraph |
|---|---|---|
| Multi-turn conversation state | Manual | Built-in (state graph) |
| Conditional branching | Awkward | Native (edges + conditions) |
| Streaming tokens + tool events | Partial | Full event stream |
| Checkpointing | No | Yes (MemorySaver / DB) |
| Human-in-the-loop | No | Yes |
| Parallel tool calls | No | Yes (Send API) |

---

### Graph — Node Definitions

```
START
  │
  ▼
[build_context]          Loads investor_profile, computes personalization_mode,
  │                      builds dynamic system prompt. Runs once per session start;
  │                      idempotent on subsequent turns.
  │
  ▼
[agent]  ◄──────────┐    LLM model reasons: does it need a tool? Or can it answer?
  │                 │
  ├─ tool calls ──► [tools]   Executes one or more tool functions in parallel.
  │                 │         Returns structured JSON results to agent.
  │                 └─────────┘
  │
  └─ final answer ──► END
                       Tokens streamed to SSE endpoint during generation.
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

The `investor_id` is injected into every tool call transparently via `config["configurable"]`.
The LLM never sees or controls it — it is a locked field in state.

---

### Tool Catalogue

Ten deterministic Python functions. Each accepts `investor_id` as a fixed parameter injected
from state (not from the LLM's output). All amounts are returned in **both** deal currency
and the investor's reporting currency.

| Tool | What it answers | Key edge cases handled |
|---|---|---|
| `get_portfolio_summary` | All positions: total committed, contributed, current value, distributions, MOIC, DPI, RVPI | Multi-currency aggregation; exited/written-off deals zeroed for current value; partial contributions shown separately |
| `get_position_detail(company)` | Single company across all rounds: cost basis, units, current value, MOIC per round + aggregate | Multi-round companies (Forgecraft: Seed/A/B); per-investor effective share price; down rounds; partial exit (Tallybook 30% secondary) |
| `get_upcoming_obligations` | Capital calls + fees with due dates; overdue items flagged | Overdue fees flagged with warning; amounts in deal and reporting currency |
| `get_distributions(company=None)` | Distributions received — gross, performance fee withheld, net | Full exit vs partial secondary; exited deal vs mark-to-zero write-off |
| `get_fee_detail(deal_or_company)` | Fee structure: deal standard vs investor's effective rates; paid + upcoming | Investor discount shown where applicable; admin fee always in USD even on non-USD deals, converted separately |
| `get_valuation_history(company)` | Full mark history: date, share price, multiple vs entry, source | Down rounds; write-offs (multiple = 0); markup and exit marks |
| `get_account_statement(start_date, end_date)` | Signed cashflow ledger: contributions (−), fees (−), distributions (+) | Date-range filtering; net cash position |
| `get_fx_rates` | Current FX rates (USD/GBP/EUR/AED) | For explicit currency conversion questions |
| `search_company(name_query)` | Disambiguate company names → matching company_id(s) | "Northpeak" returns both Northpeak Analytics and Northpeak Health; agent asks investor to confirm |
| `get_investor_profile` | Investor's own profile fields | For self-referential questions ("am I KYC verified?", "what's my reporting currency?") |

**What tools explicitly do not do:**
- Generate SQL dynamically
- Accept free-form query strings from the LLM
- Return raw database rows (they return computed, labelled JSON)
- Raise exceptions to the LLM (errors returned as `{"error": "..."}` dicts)

---

### Data Fetching Strategy

Tools use **SQLAlchemy 2.0 ORM queries** (no raw SQL). No ingestion pipeline, no embeddings, no ETL.

Each tool is a pure Python function:
```
tool_function(investor_id, **params) → dict
```

Calculations happen inside the tool before returning:
- **FX conversion:** `amount × (deal_fx.to_usd / reporting_fx.to_usd)`
- **MOIC:** `(current_value + net_distributions) / contributed_amount`
- **Current value:** `units × (1 - realised_fraction) × latest_share_price`
- **Net distribution:** `gross_amount - performance_fee_amount`

The LLM receives pre-computed, labelled results and only needs to describe them.

---

### Handling Tricky Data Cases

These cases are handled deterministically by tools — not reasoned about by the LLM:

| Case | Tool handling |
|---|---|
| Same company in multiple rounds | `get_position_detail` groups by `company_id`, returns one row per round + an aggregate. Always labels rounds explicitly ("Forgecraft Seed", "Forgecraft Series A") |
| Per-investor share-price discount | `effective_share_price` and `units` read from allocation, not deal |
| Multi-currency | Every tool converts to reporting currency using `fx_rates`. Both amounts always returned |
| Partial contribution (contributed_pct < 100) | Committed and contributed reported separately; outstanding commitment shown explicitly |
| Pending/unfunded allocation | allocation_status == 'Pending' → contributed = 0; flagged in summary |
| Zero-holding investors | `get_portfolio_summary` returns empty allocations list; no positions are fabricated |
| Exited deal (Helianthe Energy) | Current value = 0; distributions exist; MOIC = net_distributions ÷ contributed |
| Written-off deal (Yappio) | Current value = 0; multiple = 0 |
| Down round (Qubrium Series B) | latest share_price < entry_share_price; multiple_vs_entry < 1; both prices returned |
| Partial secondary (Tallybook) | realised_fraction = 0.3 → current value uses (1 − 0.3) × units × latest_price |
| Overdue fees | fees with status == 'Overdue' flagged with warning in `get_upcoming_obligations` |
| Similar company names | `search_company("Northpeak")` returns both matches; assistant asks investor to confirm |
| Admin fee currency | fee.currency == 'USD' even on GBP/EUR/AED deals; FX-converted separately |

---

### Determinism and Reliability

1. **No LLM-generated SQL.** All queries are written by the developer. The LLM only picks which tool to call. A wrong tool call returns an empty result or an error dict — it cannot corrupt data.

2. **All arithmetic in Python.** MOIC, DPI, FX conversion are computed in tool functions and are independently testable. The LLM only formats the output.

3. **Structured tool outputs.** Every tool returns a typed dict with explicitly labelled fields. The LLM cannot confuse `gross_amount` with `net_amount` because both are present and named.

4. **investor_id locked in state.** Injected into every tool call via `config["configurable"]` — the LLM never receives it as a parameter it can alter.

5. **Temperature 0.** Responses to financial questions are stable and deterministic. Personalisation affects structure and tone, not numerical output.

6. **Explicit currency labelling.** Tools always return `{"amount": 42000, "currency": "GBP"}`. The system prompt instructs the LLM to always state the currency.

7. **Explicit empty states.** Tools return `{"allocations": [], "message": "no positions found"}` rather than null/None, preventing the LLM from hallucinating missing data.

---

### Streaming Architecture

```
Browser (Next.js)
│  EventSource → /chat/{session_id}/stream?message=...
│
FastAPI (api package)
│  POST /chat/sessions                  → create session, return session_id
│  GET  /chat/{session_id}/stream       → SSE endpoint
│       yields: {"type":"thinking_delta","content":"..."}   ← reasoning chunk
│               {"type":"token","content":"..."}            ← answer text chunk
│               {"type":"tool_start","tool":"...","label":"..."}
│               {"type":"tool_end","tool":"..."}
│               {"type":"done"}
│
LangGraph agent (ai package)
│  graph.astream_events(input, config, version="v2")
│    on_chat_model_stream  → thinking/text block deltas → forwarded to SSE
│    on_tool_start         → tool name → forwarded as tool_start event
│    on_tool_end           → result stored in state; not forwarded verbatim
│
Anthropic claude-sonnet-4-6
   thinking={"type": "adaptive", "display": "summarized"}
   max_tokens=8096
```

Frontend behaviour:
- Typing indicator shown until first token or thinking delta arrives
- Tool call chips show a human-readable label while each tool runs
- Thinking content streams into a collapsible panel above the answer
- Text streams in as tokens arrive
- On `done`, message is finalised in the UI and saved to `chat_messages`

---

### LangSmith Integration

Every agent run is linked to a LangSmith trace so any conversation turn can be inspected —
full tool calls, reasoning chain, LLM payloads, and latency — via a single URL.

#### run_id capture

LangGraph's `astream_events` exposes `run_id` as a top-level field on every event (not inside
`metadata`). The API layer reads this once from the first event and writes it to `agent_runs`:

```python
run_id = None
async for event in graph.astream_events(input, config, version="v2"):
    if run_id is None:
        run_id = event.get("run_id")   # top-level field
    # forward token/tool events to SSE ...
```

#### Cost retrieval

After the stream completes, a background task queries the LangSmith SDK to fetch token counts
and compute cost. This runs asynchronously so it never delays the SSE response:

```python
from langsmith import Client as LangSmithClient

def record_run_cost(run_id_str: str):
    run = LangSmithClient().read_run(run_id_str)
    prompt_tokens     = run.prompt_tokens or 0
    completion_tokens = run.completion_tokens or 0  # includes thinking tokens
    cost_usd = (prompt_tokens * 3 + completion_tokens * 15) / 1_000_000
    # Sonnet 4.6: $3/1M input, $15/1M output (thinking billed as output)
```

#### Message linkage

| Field | Value |
|---|---|
| `agent_runs.user_message_id` | FK to the `chat_messages` row for the triggering user turn |
| `agent_runs.assistant_message_id` | FK to the `chat_messages` row for the completed assistant reply |

A single JOIN from `chat_messages → agent_runs` gives the LangSmith trace URL and cost
for any message in the history.

---

### Thinking Mode

Claude surfaces its reasoning process as a visible, streaming "thinking" block. Investors see
*why* the assistant arrived at an answer — which tools it chose to call, what conditions it
weighed, what it ruled out. This is particularly valuable for financial decisions where
transparency builds confidence in the output.

#### API configuration

```python
llm = ChatAnthropic(
    model="claude-sonnet-4-6",
    thinking={"type": "adaptive", "display": "summarized"},
    max_tokens=8096,
)
```

- `type: "adaptive"` — Claude decides how much reasoning the question warrants.
- `display: "summarized"` — thinking content is streamed as readable text. The default (`"omitted"`) returns an empty string and must be overridden.
- `budget_tokens` is deprecated on Sonnet 4.6 — sending it causes a 400 error.

#### Block types during streaming

Both thinking and answer text arrive via `on_chat_model_stream` events. Distinguish by `type`:

```python
# Thinking chunk:  {"type": "thinking", "thinking": "I need to check...", "index": 0}
# Text chunk:      {"type": "text",     "text": "Your portfolio...",       "index": 1}
# Signature block: {"type": "thinking", "signature": "...",                "index": 0}
#   ↑ marks end of thinking block — contains no display text; skip it

for block in chunk.content:
    if isinstance(block, dict):
        if block.get("type") == "thinking" and "thinking" in block:
            yield SSE("thinking_delta", block["thinking"])
        elif block.get("type") == "text" and "text" in block:
            yield SSE("token", block["text"])
```

#### SSE event mapping

| LangGraph event | SSE type | Payload |
|---|---|---|
| `on_chat_model_stream` — thinking block | `thinking_delta` | `{"type":"thinking_delta","content":"..."}` |
| `on_chat_model_stream` — text block | `token` | `{"type":"token","content":"..."}` |
| `on_tool_start` | `tool_start` | `{"type":"tool_start","tool":"...","label":"..."}` |
| `on_tool_end` | `tool_end` | `{"type":"tool_end","tool":"..."}` |
| stream complete | `done` | `{"type":"done"}` |

#### Persistence

The completed thinking summary is stored in `chat_messages.thinking_content` for every
assistant turn. When a user reloads the chat history, the thinking panel is restored from
this field in its collapsed state. Thinking content is stored alongside but retrieved
separately from the answer — it is never rendered inline in the response text.

#### Frontend — collapsible reasoning panel

```
┌─────────────────────────────────────────────────────────┐
│  [▶ See reasoning]  ← collapsed by default              │
│                                                         │
│  ▼ Expanded:                                            │
│  ┌─────────────────────────────────────────────────┐   │
│  │ I need to check the investor's allocations to   │   │
│  │ calculate MOIC. I'll call get_portfolio_summary  │   │
│  │ first. The user's reporting currency is GBP...  │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  Your overall MOIC is 1.8×, meaning your investments    │
│  have grown to 1.8 times what you put in...             │
└─────────────────────────────────────────────────────────┘
```

- The panel streams `thinking_delta` events in real time alongside tool calls.
- The final answer streams below once `token` events begin.
- Expand/collapse state is persisted in `localStorage` per session.

---

### Personalisation System

**Principle:** Same numbers for everyone. Different depth, tone, and framing.

#### Computing personalization_mode at session start

```
Input signals:
  tech_savviness : Low | Medium | High     (stored on investor)
  age            : integer or null          (null for entity investors)
  deal_count     : count(allocations)       (derived at session start)

Scoring:
  +2  tech_savviness == High
  +1  tech_savviness == Medium
  +1  deal_count >= 5
  +1  age < 50
  −1  age >= 65

Mode:
  score >= 3  →  "expert"
  score == 2  →  "standard"
  score <= 1  →  "simplified"
```

#### Building the personalised system prompt

Constructed once at session start and injected into every LLM call.

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

**Tone — "simplified":**
```
- Use plain English. Avoid jargon. If you must use a term like MOIC, explain it in parentheses:
  "MOIC (how many times their money has grown)".
- Lead with the bottom line, then supporting detail.
- Use concrete language: "you have earned £X back" rather than "realised DPI of 1.5×".
- Be warm and reassuring in tone, never condescending.
```

**Tone — "standard":**
```
- Clear professional language. Define terms that are not everyday vocabulary.
- Structure answers with a headline figure, then a brief breakdown.
- Reference the investor's most active sectors where relevant: {top_sectors}.
```

**Tone — "expert":**
```
- Be concise and data-dense. Assume fluency with MOIC, DPI, RVPI, carry, SPV, SAFE.
- Lead with key metrics. Use tables where multiple positions are compared.
- No need to define standard VC/PE vocabulary.
- Reference portfolio concentration and cross-round positions where relevant.
- The investor holds {deal_count} positions across {sector_summary}.
```

Beyond tone, the LLM is instructed to reference the investor's most active sectors in
portfolio-level answers, adapt framing to what they actually hold (flag overdue fees early,
lead with realised proceeds if an exit exists), and always show per-round and aggregate views
for multi-round holdings.

---

## API Design

```
# Health
GET  /health

# Investors
GET  /investors                   paginated list
GET  /investors/{id}              full profile including top_sectors, deal_count
GET  /investors/{id}/allocations  all positions for one investor
GET  /investors/{id}/statement    cashflow ledger

# Deals
GET  /deals                       paginated list
GET  /deals/{id}

# Portfolio companies
GET  /portfolio-companies         list with totals
GET  /portfolio-companies/{id}

# AI Chat
GET  /chat/investors              dropdown list (id, name, reporting_currency)
POST /chat/sessions               body: {investor_id} → {session_id, investor_name, reporting_currency}
GET  /chat/{session_id}/stream    SSE — primary chat endpoint; ?message=<text>
GET  /chat/{session_id}/messages  full history for reload
```

Full interactive documentation is available at `/docs` (Swagger UI) when the service is running.

---

## Frontend

### Dashboard (`/`)

The dashboard serves as the simulated entry point to the platform. A persistent banner
explains that investor selection replaces a real authentication flow. The layout is two-column
on desktop, stacked on mobile:

**Left — Sign in as investor**
- Investor dropdown populated from `GET /chat/investors`
- On selection, the investor's profile is fetched and rendered as a preview card:
  avatar, name, type, country, reporting currency, KYC status badge, deal count,
  experience level, and top sector tags
- "Enter portfolio →" creates a session and navigates to the chat page

**Right — Platform overview**
- Live stats (investor count, company count, deal count) fetched from the API
- List of assistant capabilities with descriptions — sets expectations before entering chat

### Chat page (`/chat`)

Full-height layout. URL parameters carry `session`, `name`, and `currency` from the dashboard.

```
┌─────────────────────────────────────────────────┐
│  [Avatar] Investor Name  ·  USD       [Change]  │  ← session info bar
├─────────────────────────────────────────────────┤
│                                                 │
│  [▶ See reasoning]                              │  ← ThinkingPanel (streams live)
│  ┌──────────────────────────────────────────┐   │
│  │  Assistant response with markdown        │   │  ← ReactMarkdown (tables, bold, lists)
│  └──────────────────────────────────────────┘   │
│                                                 │
│                    User message  ►              │
│                                                 │
│  [Fetching your positions…  ⟳]                  │  ← ToolStatusChip (during tool calls)
│                                                 │
├─────────────────────────────────────────────────┤
│  [ Ask anything about your portfolio…      ▶ ]  │  ← ChatInput (auto-resize, Enter to send)
└─────────────────────────────────────────────────┘
```

**Components:**
- `ThinkingPanel` — streams reasoning in real time; collapsed by default; expand state persisted in localStorage
- `ToolStatusChip` — animated spinner with human-readable label for each active tool call
- `MessageList` — user messages right-aligned (indigo); assistant messages left-aligned (white card); ReactMarkdown with custom component overrides for tables, headers, code blocks
- `ChatInput` — auto-resizing textarea; Enter to send, Shift+Enter for newline; disabled while streaming
- `useChatStream` hook — EventSource with 50ms flush interval to batch token updates; handles `thinking_delta`, `token`, `tool_start`, `tool_end`, `done`, `error`; cleans up EventSource on unmount

Empty state shows a greeting and four starter prompts. On first assistant response, the prompt grid is replaced by the message thread.

---

## Startup Sequence

```
postgres (healthy)
    └─► api container entrypoint:
            1. alembic upgrade head   (idempotent)
            2. python -m common.seed  (idempotent — ON CONFLICT DO NOTHING)
            3. uvicorn api.main:app   (port 8000)
redis (healthy)
    └─► worker container:
            celery -A api.celery_app worker
frontend:
    └─► next start  (port 3000)
```

No manual steps are required after `docker compose up --build`.

---

## Decision Log

| Question | Decision | Reason |
|---|---|---|
| RAG / vector search? | No | Data is structured SQL, not unstructured documents. Tools give exact results; RAG adds noise over financial figures. pgvector is installed and available if free-text company notes or a help knowledge base are added later. |
| Text-to-SQL? | No | LLM-generated SQL is non-deterministic for financial calculations. Pre-built tools are correct by construction and independently testable. |
| Agent type? | LangGraph ReAct | Multi-step data composition, conversation state, full streaming, and future extensibility (human-in-the-loop, clarification nodes) all favour LangGraph over a fixed LCEL chain. |
| New DB tables? | chat_sessions + chat_messages + agent_runs only | All investor and portfolio data is in the existing schema. No ETL, no embeddings, no new fact tables. |
| Arithmetic in LLM? | Never | All MOIC / DPI / FX maths lives in Python tool functions. The LLM only formats prose from pre-computed results. |
| investor_id security | Locked in graph state | The LLM cannot escape an investor's data scope. investor_id is injected at every tool call via `config["configurable"]`, never passed as an LLM output parameter. |
| LLM temperature | 0 | Financial responses must be stable. Personalisation is in the system prompt; stochasticity is not needed or desirable. |
| Conversation memory | LangGraph MemorySaver + Postgres persistence | MemorySaver maintains full LangGraph state for live sessions. chat_messages provides durable, queryable history for reload and audit independent of process restarts. |
| Streaming protocol | Server-Sent Events (SSE) | Simpler than WebSockets for unidirectional server → client streams; native browser EventSource; no custom protocol handshake. |
| LLM model selection | claude-sonnet-4-6 | Three factors: (1) adaptive thinking is supported, which is the key capability for the reasoning panel; (2) the model's actual role is tool routing and prose narration — all arithmetic and data fetching is handled by Python tool functions, so frontier reasoning is not required; (3) Sonnet 4.6 is $3/$15 per 1M tokens vs Opus 4.8 at $5/$25 — at ~6,000 input + ~800 output tokens per turn the cost difference is meaningful at scale while capability is sufficient for the task. Upgrade to Opus 4.8 if open-ended advisory features (portfolio recommendations, comparative analysis) are added and tool routing becomes genuinely ambiguous. |
| Thinking mode API | `thinking: {type: "adaptive", display: "summarized"}` | `budget_tokens` is deprecated on Sonnet 4.6 (causes 400 errors). Adaptive thinking lets Claude calibrate reasoning depth per question. `display: "summarized"` is required to receive thinking content — the default (`"omitted"`) returns an empty string. |
| Thinking UX | Collapsible panel, streams live | Thinking content is visually separated from the answer so it does not interrupt reading. Collapsed by default so users see the answer first; available for those who want to verify the reasoning. |
| LangSmith tracing | agent_runs table + background cost fetch | Storing trace URL and token cost per agent run gives end-to-end debugging and cost visibility without adding latency to the SSE response. A single JOIN from chat_messages to agent_runs returns the LangSmith trace for any conversation turn. |

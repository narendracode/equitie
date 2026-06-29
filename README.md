# EquiTie

**AI-powered investor platform**

---

## Walkthrough
You can find the video walkthrough here : https://drive.google.com/file/d/1UGFZS6406g2Lp8R7QsIFL_du21LkOokg/view?usp=sharing

## Prerequisites

You need **Docker** and **Make** installed before running the project.

### macOS

```bash
# Docker Desktop (includes Docker Compose)
brew install --cask docker

# Make (included with Xcode Command Line Tools)
xcode-select --install
```

Or download Docker Desktop directly from https://www.docker.com/products/docker-desktop

### Windows

**Docker Desktop:**
Download and install from https://www.docker.com/products/docker-desktop
Enable WSL 2 backend during installation (recommended).

**Make:**
The easiest option is via [Chocolatey](https://chocolatey.org):
```powershell
# Run in PowerShell as Administrator
choco install make
```
Alternatively, install [Git for Windows](https://gitforwindows.org) — it includes `make` via Git Bash.

> All `make` commands should be run from the repo root. On Windows, use Git Bash or WSL 2 terminal, not PowerShell.

---

## Quick Start

```bash
# 1. Clone and enter the repo
git clone https://github.com/narendracode/equitie.git && cd equitie

# 2. Copy environment variables
cp .env.example .env
# Add your ANTHROPIC_API_KEY (and optionally LANGSMITH_API_KEY) to .env

# 3. Start all services
make up
```

Once running:

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| API + Swagger | http://localhost:8000/docs |
| Postgres | localhost:5432 |
| Redis | localhost:6379 |

The startup sequence is fully automatic: migrations run, the database seeds, and all services start in the correct order. No manual steps required.

---

## What It Does

- **Portfolio Q&A** — Ask questions about positions, valuations, MOIC, distributions, and fees in plain English
- **Personalised responses** — Communication style adapts to each investor's profile (simplified / standard / expert)
- **Proactive context** — Multi-round companies, partial contributions, FX conversion, and edge cases handled automatically
- **Scope isolation** — Every response is strictly scoped to the authenticated investor; no data leakage across accounts
- **Streaming** — Responses stream token-by-token with a visible thinking panel and live tool-call status

---

## Project Structure

```
EquiTie/
├── packages/
│   ├── common/       SQLAlchemy models, Alembic migrations, seed script
│   ├── ai/           LangGraph agent, tools, personalisation logic
│   └── api/          FastAPI app, routers, Celery tasks
├── frontend/         Next.js 14 + Tailwind CSS
├── data/             Seed CSVs (synthetic, read-only)
├── docker-compose.yml
└── Makefile
```

Package dependency: `api → common`, `api → ai`, `ai → common`.

---

## Documentation

| Document | What's inside |
|---|---|
| [`system_design.md`](./system_design.md) | Architecture decisions, data model, agent design, tool contracts, evaluation layers |
| [`RUNNING.md`](./RUNNING.md) | Full setup guide, all `make` commands, test layer reference, troubleshooting |
| [`DEMO_VERIFICATION.md`](./DEMO_VERIFICATION.md) | Manual verification steps with expected values — used to confirm the AI assistant produces correct numbers |
| [`roadmap.md`](./roadmap.md) | Six-month plan for the full relationship-manager bot: scope, architecture, team, timeline, and costs |
| [`ai-workflow.md`](./ai-workflow.md) | How AI was used in development, what was accepted or changed, and how output quality was verified |

---

## Running Tests

Prerequisites: `make up-d` (Docker running) and `make install` (local venv).

```bash
make test-tools      # Layer 1: 26 tool edge-case tests — fast, free, no LLM
make test-eval       # Layer 2: number fidelity evals — LLM-as-judge (requires ANTHROPIC_API_KEY)
make test-routing    # Layer 3: tool routing golden set
make test-scope      # Layer 4: scope isolation — adversarial prompts
make test-persona    # Layer 5: personalisation compliance — LLM-as-judge
make test-all        # All layers combined (It takes little longer to complete.)
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| API | Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic |
| AI agent | LangGraph · Anthropic Claude (claude-sonnet-4-6) |
| Streaming | FastAPI SSE · EventSource (browser) |
| Task queue | Celery + Redis |
| Database | PostgreSQL 16 + pgvector |
| Frontend | Next.js 14 (App Router) · Tailwind CSS |
| Packaging | UV workspaces (monorepo) |
| Infrastructure | Docker Compose |

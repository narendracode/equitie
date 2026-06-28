# AI Workflow

## Which AI tools and models did you use, and for what?

**Development environment:** Claude Sonnet 4.6 (`claude-sonnet-4-6`) via Claude Code was used throughout the development lifecycle — from scaffolding the monorepo structure and database schema, to implementing the LangGraph agent, writing deterministic tool functions, and building the test evaluation layers.

**Application AI assistant:** The investor-facing assistant also runs on Claude Sonnet 4.6. It was selected for its strong instruction-following and reasoning capabilities, which are essential for a multi-tool ReAct agent that must handle nuanced investor queries, enforce scope isolation across a multi-investor dataset, and adapt its communication style based on investor profile.

---

## Roughly what percentage of the code was AI-generated?

Approximately **90%** of the code is AI-generated. My role was that of the architect: I defined the system design, established the data model, set the architectural constraints (LLM does language, Python does maths — no SQL generation, no LLM arithmetic), and owned the quality bar end-to-end. The AI operated as a high-velocity implementation partner within those boundaries. Every batch of generated code was reviewed and accepted, adjusted, or rejected before being considered complete.

---

## What did you reject or materially change from AI suggestions, and why?

Rather than posing open-ended problems to the AI and accepting its solutions wholesale, I led from the front: the architecture, data edge cases, tool contracts, and evaluation strategy were all designed upfront (documented in `system_design.md`), and the AI was directed to implement within that specification.

Key areas where I exercised strong editorial judgement:

- **Tool return contracts** — enforced a strict `dict`-only return type with dual-currency amounts on every tool, overriding any tendency toward ad-hoc response shapes.
- **Personalisation prompts** — the initial simplified-mode system prompt was too vague; the LLM defaulted to markdown tables and left domain terms unexplained. I diagnosed this through the LLM-as-judge eval layer and rewrote the prompt with an explicit vocabulary list and structural constraints.
- **Scope isolation** — I drove the decision that `investor_id` must be injected from authenticated session state and must never appear in any tool's input schema. This is a security invariant, not a convenience, and I verified it with adversarial test cases rather than trusting the implementation at face value.

The overall approach was to work in small, reviewable increments — specify → generate → verify → iterate — rather than delegating large unsupervised chunks.

---

## How did you verify the assistant's answers were correct?

Verification was layered, moving from fast deterministic checks to expensive probabilistic evals:

| Layer | What it checks | Speed | Cost |
|---|---|---|---|
| Layer 1 — Tool unit tests | 26 edge cases covering all data anomalies (partial contributions, multi-round positions, written-off deals, FX conversion, etc.) | Fast | Free |
| Layer 2 — Number fidelity evals | Claude-as-judge confirms every figure in a live agent response traces to a real tool output | Slow | ~$0.03/case |
| Layer 3 — Tool routing | Golden-set of 20 questions verifies the agent calls the correct tool(s) | Slow | ~$0.02/case |
| Layer 4 — Scope isolation | Adversarial prompts (cross-investor requests, prompt injection, named investor requests) confirm the agent never leaks data | Slow | ~$0.05/case |
| Layer 5 — Personalisation compliance | LLM-as-judge scores responses against mode-specific rubrics; style contrast test confirms simplified and expert modes produce genuinely different output | Slow | ~$0.29/run |

For manual end-to-end verification, a representative investor (Idris Olawale, INV001) was selected and three demo questions were answered by hand — computing MOIC, Forgecraft multi-round breakdowns, and upcoming obligations from raw database values — and then cross-checked against the live assistant. The full calculation workings are in [`DEMO_VERIFICATION.md`](./DEMO_VERIFICATION.md).

---

## If you had an autonomous coding agent for another 8 hours, what would you point it at next?

**1. Online learning and feedback loops**
Introduce a reward/penalty mechanism so the assistant improves with use. User feedback signals (thumbs up/down, follow-up corrections) would be logged and used to fine-tune the system prompt, tool selection heuristics, or retrieval strategies over time — making the assistant measurably better rather than static.

**2. Intelligent model routing to manage cost at scale**
The current architecture routes every query through Claude Sonnet 4.6 regardless of complexity. At volume this becomes expensive. A supervisor layer that classifies query intent and routes simple factual lookups to a lighter model (e.g. Haiku) while reserving Sonnet for multi-step reasoning would substantially reduce inference costs without degrading answer quality.

**3. Benchmarking and regression suite**
Build a structured benchmark corpus — a fixed question set with known correct answers — and run it on every code change. This turns the current manual demo verification into a continuous, automated quality gate and provides a quantitative baseline for measuring the impact of any future model or prompt changes.

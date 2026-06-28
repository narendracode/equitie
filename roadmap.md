# ~Six-Month Roadmap

---

## Why I Care About This Problem

Having run multiple ventures, I have first-hand experience of the operational overhead that comes with building a company — engaging agencies for incorporation, working with company secretaries, managing accounting, staying on top of compliance. One product that genuinely changed that experience for me was **Osome**: a single mobile app that brought all of those services together so I never had to leave the platform to get things done.

That experience stuck with me, and when I look at EquiTie, I see exactly the same opportunity on the investor side. Today, investors navigate a fragmented landscape — fragmented comms, fragmented documents, fragmented updates — and a human relationship manager is the glue holding it together. This roadmap is about replacing that fragmentation with a single, intelligent surface. My goal is to build the greatest app any investor has ever used to work with the startups they back.

---

## Philosophy: AI as a Multiplier

Before addressing specifics, a framing principle: AI should function as an organisational multiplier, not a feature. The goal is not to bolt a chatbot onto the product, but to build a system where humans and agents collaborate at every layer — business, product, and engineering — each doing what they do best.

This shapes every architecture and hiring decision that follows. The RM bot is the customer-facing expression of that philosophy; the underlying data platform and agentic workflows are what make it sustainable and defensible.

---

## 1. Scope and Capabilities

### What the bot does

| Capability | Description |
|---|---|
| **Portfolio Q&A** | Answers investor questions about positions, valuations, MOIC, distributions, fees — personalised to the investor's profile and reporting currency |
| **Proactive nudges** | Push notifications for upcoming capital calls, overdue fees, document deadlines, and valuation updates — without the investor having to ask |
| **Capital call and fee reminders** | Structured reminders with amounts, due dates, and payment instructions; escalation to human RM if unpaid after N days |
| **KYC and document requests** | Collects and tracks required KYC documents; sends targeted requests, chases outstanding items, and confirms completion |
| **Investor onboarding** | Guides new investors through subscription documents, KYC/AML, bank account setup, and first capital call — end-to-end in-app |
| **Reporting on demand** | Generates personalised portfolio reports, account statements, and tax summaries on request or on schedule |
| **Drafting investor comms** | First-draft quarterly updates, distribution notices, and deal announcements for human RM review before sending |
| **Meeting prep** | Summarises portfolio performance, outstanding items, and recent activity ahead of investor calls |
| **In-app messaging** | Investors never need to leave the app; the bot handles routine queries and hands off to a human RM in-thread when needed |

### What stays with a human

Human RMs retain ownership of: investment advice and recommendations, legal document signing, relationship exceptions and disputes, complex fund structuring questions, and final approval on all outbound investor communications. The bot drafts and prepares; the human decides and signs off. This is both a trust design and a regulatory requirement.

---

## 2. Architecture and Tech Stack

### End-to-end stack

```
React Native app (iOS + Android)  Web app (Next.js 14 + Tailwind)
         │                                    │
         └──────────────┬─────────────────────┘
                        │ HTTPS / WebSocket / SSE
                 API Gateway (AWS ALB)
                        │
          ┌─────────────┴──────────────┐
     FastAPI (Python 3.12)        Celery workers
     LangGraph agent              (async tasks: nudges,
     Tool layer (deterministic)    report generation,
     Auth.                        KYC chasing)
          │
    PostgreSQL                Redis (queue + cache)
          │
    EquiTie Lakehouse (S3 + Delta Lake / Iceberg)
    Medallion: Bronze (raw) → Silver (clean) → Gold (business-ready)
    Unified query layer: DuckDB
```

### Component choices and rationale

| Component | Choice | Why |
|---|---|---|
| **Orchestration** | LangGraph (multi-agent, supervisor routing) | Already proven in prototype; handles complex multi-step tool use with state |
| **Primary model** | Claude Sonnet 4.6 (complex reasoning) + Haiku 4.5 (simple lookups) | Cost-routing: supervisor classifies intent and routes; target is LLM cost parity with a database call over time |
| **Model hosting** | Anthropic API (primary) + open-source fallback (Llama / Mistral on-prem or Bedrock) | Avoids single-vendor lock-in; critical for availability SLA |
| **Retrieval** | pgvector for semantic document search; deterministic SQL tools for all numerical data | LLM never does arithmetic; every figure traces to a tool output |
| **Auth** | Auth0 (OIDC, 2FA, MFA) — buy, not build | Certification-ready out of the box; not our core competency |
| **Observability** | OpenTelemetry → Grafana stack; LangSmith for LLM tracing | No system ships to production without metrics and alerting; infra-as-code (Terraform + Helm) for reproducibility |
| **CI/CD** | GitHub Actions → Docker → Kubernetes (EKS or GKE) | Auto-scaling, elastic, cost-optimised; one-time setup effort |
| **Mobile** | React Native (hybrid iOS + Android) | Single codebase covers both platforms; shares business logic and API layer with the web app; native modules available for voice and push where needed |
| **Security** | AWS KMS for secrets; VPC isolation per tenant; PII tokenisation before LLM calls | Multi-tenancy and enterprise data isolation from day one |

### Evaluation pipeline

Every model change triggers: tool unit tests (fast, free) → number fidelity evals (LLM-as-judge) → routing regression suite → personalisation compliance (LLM-as-judge). A/B model testing in staging allows quality-vs-cost measurement before production rollout. Over time, fine-tuned models on investor domain data reduce inference costs without sacrificing accuracy.

---

## 3. Data and Integrations

### Lakehouse as the foundation

All source systems write to the **Bronze** layer (raw, immutable). Cleaning and normalisation produces the **Silver** layer. Business-ready aggregations (portfolio metrics, investor views, audit logs) live in **Gold**. Agents and analytics tools query Gold; raw integrations write to Bronze. This decouples the RM bot from source system churn.

### Integration map

| System | Integration type | Data flowing in | Data flowing out |
|---|---|---|---|
| **Portfolio ledger** (internal) | Direct DB / API | Allocations, capital calls, distributions, valuations | — |
| **Fund administration** (Carta / Juniper Square) | REST API + webhook | NAV, fee calculations, investor statements | Capital call notices |
| **CRM** (HubSpot or Salesforce) | Bidirectional API | Investor profile, interaction history | Bot conversation summaries, action items |
| **KYC/AML** (Onfido or Jumio — buy) | REST API | KYC status, document verification results | Document requests, status updates |
| **E-signature** (DocuSign — buy) | REST API + webhook | Signed document status | Subscription docs, KYC forms |
| **Comms** (SendGrid / email, push) | SDK | Delivery receipts | Notifications, nudges, reports |
| **Calendar** (Google / Microsoft) | OAuth + API | Meeting schedules | Pre-meeting briefings |
| **Market / valuation data** (PitchBook, Crunchbase) | API | Comparable valuations, company data | — |
| **Document storage** | S3 + versioning | All uploaded documents | Signed, processed documents |

---

## 4. AI Approach and Safety

### Core principle (carried from prototype)

**LLM does language. Python does maths.** The model never generates SQL, never does arithmetic, and never invents figures. Every number in a response originates from a deterministic tool function. This is non-negotiable and the single most important guardrail against hallucination in a financial context.

### Grounding and retrieval

- **Numerical data**: tool functions query the database directly and return structured dicts
- **Document intelligence**: fund documents, KYC policies, and legal agreements are chunked and stored in pgvector; RAG retrieves relevant passages before the LLM drafts responses
- **No retrieval needed**: portfolio metrics are always computed fresh from source data, not retrieved from a vector store

### Multi-agent architecture

A **supervisor agent** classifies incoming queries and routes them to specialist sub-agents:
- *Portfolio agent* — Q&A, metrics, performance
- *Obligations agent* — capital calls, fees, overdue items
- *Document agent* — KYC, onboarding, e-signature workflows
- *Comms agent* — drafting investor updates, meeting prep
- *Escalation agent* — detects when a human RM must be looped in

### Guardrails and compliance

| Guardrail | Implementation |
|---|---|
| No investment advice | System prompt hard constraint + output classifier detects advice-giving language |
| PII protection | PII tokenisation before any data reaches the LLM; de-tokenisation on output |
| Audit trail | Every tool call, LLM response, and user action logged immutably with timestamp and investor ID |
| Data residency | Tenant data isolated in separate VPC namespaces; no co-mingling |
| Regulatory | SOC 2 Type II, GDPR, and (where applicable) FINRA/FCA compliance built into data handling from day one; penetration testing quarterly |
| Model data usage | Enterprise agreements with Anthropic (zero data retention / no training on customer data); open-source fallback as additional protection |

---

## 5. Team and Hiring

Hiring is sequenced to maximise early velocity, then depth.

| # | Role | Seniority | When | Rationale |
|---|---|---|---|---|
| 1 | AI/Full-Stack Engineer | ~6 years | Month 1 | Second builder; accelerates agent and API development immediately |
| 2 | Forward Deployed Engineer | ~4 years | Month 1 | Customer-facing integrations and onboarding; bridges product and engineering |
| 3 | Data Engineer | ~5 years | Month 2 | Lakehouse setup, integration pipelines, and unified query layer |
| 4 | ML / AI Researcher | 7–10 years | Month 3 | Model evaluation, fine-tuning strategy, retrieval quality, long-term cost optimisation |
| 5 | Product Designer (with mobile skills) | ~5 years | Month 3 | Mobile app UX, investor-facing flows, design system |
| 6 | Mobile Engineer (React Native) | 3–5 years | Month 4 | Hybrid iOS + Android app development once designs are ready |

The founding team (lead engineer + hire #1 and #2) does the heavy lifting in months 1–3. Research and mobile depth comes in once the foundation is solid and requirements are better defined by real usage.

---

## 6. Six-Month Timeline

> Though i believe it can be driven much faster.

### Phase 1 — Foundation (Months 1–2)

- Harden authentication (Auth0, 2FA, session management)
- Observability stack live (metrics, alerting, LLM tracing)
- Lakehouse Bronze/Silver layer for portfolio and investor data
- Core RM agent (portfolio Q&A, personalised mode) in production
- Proactive nudges: capital call and fee reminders via push notification
- CI/CD pipeline and Kubernetes deployment

**Milestone:** First real investor uses the in-app assistant; zero production incidents for 2 weeks.

### Phase 2 — Document and Compliance Layer (Months 2–4)

- KYC module: document collection, Onfido/Jumio integration, status tracking
- E-signature integration (DocuSign) for subscription docs and onboarding
- Investor onboarding flow end-to-end in-app
- RAG over fund documents (PPM, LPA, quarterly reports)
- Investor comms drafting (quarterly updates, distribution notices) — human-reviewed before send
- PII tokenisation and audit trail logging
- SOC 2 Type II audit preparation begins

**Milestone:** A new investor completes KYC, signs subscription documents, and receives first capital call — entirely in-app with no email or manual RM intervention.

### Phase 3 — Intelligence and Scale (Months 4–6)

- Multi-agent supervisor routing with specialist sub-agents
- A/B model testing framework live; Haiku routing for simple queries
- Fine-tuning exploratory work on investor domain vocabulary
- React Native app (hybrid iOS + Android) replaces web-only experience
- Voice input for the assistant
- CRM bidirectional sync (HubSpot/Salesforce)
- Meeting prep agent (summary of portfolio, outstanding items, recent activity)
- Multi-tenancy enforcement; enterprise tier isolation
- Marketing site and self-serve provisioning
- SOC 2 Type II certification target

**Milestone:** End-to-end relationship management for 50 active investors handled with zero human RM intervention for routine items; human involvement limited to advice, legal sign-off, and escalations.

---

## 7. Risks, Build vs Buy, and Cost

### Key risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| **Model vendor dependency** | High | Hybrid model strategy: Anthropic as primary, open-source (Llama/Mistral on Bedrock) as hot fallback; no single-vendor lock-in |
| **Customer data used for LLM training** | Medium | Enterprise zero-retention agreements; on-prem open-source fallback for highest-sensitivity data |
| **Regulatory / compliance exposure** | High | No investment advice guardrail from day one; SOC 2 in scope from month one, not bolted on later |
| **Hallucination on financial data** | Medium | Deterministic tool layer; LLM never does arithmetic; fidelity eval suite catches regressions |
| **Scope creep** | High | Phased plan with shipped milestones; defer nice-to-haves (voice, market data) to Phase 3 |
| **Investor trust** | Medium | Human-in-the-loop for all outbound comms; clear "drafted by AI, approved by your RM" labelling |

### Build vs buy decisions

| Decision | Call | Reason |
|---|---|---|
| KYC/AML | **Buy** | Regulated space; certification maintenance is a full-time job; providers handle liveness checks and document parsing |
| E-signature | **Buy** (DocuSign) | Legal weight, audit trail, and integrations already exist |
| Authentication | **Buy** (Auth0) | 2FA, OIDC, MFA — not our core competency; Auth0 is SOC 2 certified |
| Observability | **Buy** (Grafana, Langsmith, Opentelemetry) | Faster to value than self-hosted; elastic billing |
| Portfolio tools and RM agent | **Build** | Core IP and competitive moat; must be deterministic and auditable |
| Lakehouse | **Build on open standards** (Delta Lake / Iceberg on S3) | Avoid proprietary lock-in; leverage existing open tooling |
| Fund administration | **Integrate**  | Complex regulated space; these are the market incumbents |

### Cost shape (six-month estimate)

| Category | Estimated cost |
|---|---|
| Team (6 hires, phased) | ~£400–550k |
| Cloud infrastructure (AWS/GCP, Kubernetes, S3) | ~£3–6k/month → £20–35k total |
| LLM inference (Anthropic API) | Starts ~£1–2k/month; target reduction to ~£0.50/1,000 queries via Haiku routing and fine-tuning |
| Third-party services (Auth0, DocuSign, KYC, Datadog) | ~£3–5k/month → £20–30k total |
| SOC 2 audit preparation | ~£15–25k one-time |
| **Six-month total** | **~£500–650k** |

**Token economics:** LLM cost scales with usage, so pricing strategy must reflect this. Options: (a) per-query consumption model billed to the fund, (b) flat-fee tier per investor, (c) hybrid where basic Q&A is included and heavy automation (report generation, bulk comms) is metered. Clarity on token ownership and usage policy is a commercial requirement that should be resolved in Phase 1, not deferred.

The long-term goal is to drive LLM inference cost to parity with a database call — achieved through a combination of intelligent routing (Haiku for simple, Sonnet for complex), prompt optimisation, and domain fine-tuning. The evaluation framework built in the prototype is the foundation for measuring progress against that goal.

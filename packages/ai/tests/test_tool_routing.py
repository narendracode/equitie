"""
Layer 3 eval: tool routing accuracy.

For each question the agent is invoked end-to-end and the tools it actually called
are compared against a golden set. A case passes when every tool in `required_tools`
appears somewhere in the call trace; additional tool calls are allowed (the agent
may legitimately call search_company_tool before position_detail_tool, for instance).

Requirements:
    ANTHROPIC_API_KEY must be set
    DATABASE_URL must point at the seeded database

Cost: ~$0.03–$0.05 per case × 20 cases ≈ $0.60–$1.00 per full run.
Run time: ~15–25 s per case → ~6–8 minutes total.

Usage:
    make test-routing                           # all 20 cases
    make test-routing-k k=portfolio_summary     # single case by ID keyword
"""

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import pytest
from langchain_core.messages import HumanMessage

# ── .env loading ─────────────────────────────────────────────────────────────

try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).parents[4] / ".env"
    if _env_path.exists():
        load_dotenv(_env_path, override=False)
except ImportError:
    pass

if not os.getenv("ANTHROPIC_API_KEY"):
    pytest.skip(
        "ANTHROPIC_API_KEY not set — skipping routing evals.",
        allow_module_level=True,
    )

from ai.agent import build_graph  # noqa: E402
from tests.eval_utils import extract_called_tool_names  # noqa: E402

# ── Golden routing cases ──────────────────────────────────────────────────────

@dataclass
class RoutingCase:
    id: str
    investor_id: str
    question: str
    required_tools: frozenset[str]


ROUTING_CASES: list[RoutingCase] = [
    # ── portfolio_summary_tool ────────────────────────────────────────────────
    RoutingCase(
        id="portfolio_summary_overview",
        investor_id="INV001",
        question="What is my overall portfolio performance — MOIC, DPI, and RVPI?",
        required_tools=frozenset({"portfolio_summary_tool"}),
    ),
    RoutingCase(
        id="portfolio_summary_totals",
        investor_id="INV001",
        question="How much have I committed and contributed in total across all my deals?",
        required_tools=frozenset({"portfolio_summary_tool"}),
    ),

    # ── position_detail_tool ─────────────────────────────────────────────────
    RoutingCase(
        id="position_detail_multi_round",
        investor_id="INV001",
        question="How is my Forgecraft Robotics investment performing across all rounds?",
        required_tools=frozenset({"position_detail_tool"}),
    ),
    RoutingCase(
        id="position_detail_written_off",
        investor_id="INV010",
        question="What happened to my Yappio investment?",
        required_tools=frozenset({"position_detail_tool"}),
    ),
    RoutingCase(
        id="position_detail_exited",
        investor_id="INV011",
        question="What returns did I receive from Helianthe Energy?",
        required_tools=frozenset({"position_detail_tool"}),
    ),
    RoutingCase(
        id="position_detail_down_round",
        investor_id="INV004",
        question="How is my Qubrium Series B position doing?",
        required_tools=frozenset({"position_detail_tool"}),
    ),
    RoutingCase(
        id="position_detail_partial_secondary",
        investor_id="INV013",
        question="What is my Tallybook position worth and how much have I already realised?",
        required_tools=frozenset({"position_detail_tool"}),
    ),

    # ── search_company_tool — disambiguation is the primary objective ─────────
    RoutingCase(
        id="search_disambiguation",
        investor_id="INV001",
        question="Tell me about my Northpeak investment.",
        required_tools=frozenset({"search_company_tool"}),
    ),

    # ── upcoming_obligations_tool ─────────────────────────────────────────────
    RoutingCase(
        id="obligations_upcoming",
        investor_id="INV001",
        question="What capital calls do I have scheduled in the coming months?",
        required_tools=frozenset({"upcoming_obligations_tool"}),
    ),
    RoutingCase(
        id="obligations_overdue",
        investor_id="INV001",
        question="Do I have any overdue fees or missed payments?",
        required_tools=frozenset({"upcoming_obligations_tool"}),
    ),

    # ── distributions_tool ────────────────────────────────────────────────────
    RoutingCase(
        id="distributions_all",
        investor_id="INV001",
        question="What distributions have I received across my portfolio?",
        required_tools=frozenset({"distributions_tool"}),
    ),
    RoutingCase(
        id="distributions_company",
        investor_id="INV011",
        question="How much did I receive from Helianthe Energy distributions?",
        required_tools=frozenset({"distributions_tool"}),
    ),

    # ── fee_detail_tool ───────────────────────────────────────────────────────
    RoutingCase(
        id="fee_detail_overview",
        investor_id="INV001",
        question="What management and performance fees am I paying across my deals?",
        required_tools=frozenset({"fee_detail_tool"}),
    ),
    RoutingCase(
        id="fee_detail_company",
        investor_id="INV001",
        question="What are the fee details and rates on my Forgecraft deals?",
        required_tools=frozenset({"fee_detail_tool"}),
    ),

    # ── valuation_history_tool ────────────────────────────────────────────────
    RoutingCase(
        id="valuation_history_yappio",
        investor_id="INV010",
        question="Show me the full valuation mark history for Yappio.",
        required_tools=frozenset({"valuation_history_tool"}),
    ),
    RoutingCase(
        id="valuation_history_trend",
        investor_id="INV004",
        question="How has the Qubrium share price changed over time?",
        required_tools=frozenset({"valuation_history_tool"}),
    ),

    # ── account_statement_tool ────────────────────────────────────────────────
    RoutingCase(
        id="account_statement_full",
        investor_id="INV001",
        question="Show me my full account statement.",
        required_tools=frozenset({"account_statement_tool"}),
    ),
    RoutingCase(
        id="account_statement_filtered",
        investor_id="INV001",
        question="What were my cashflows and transactions during 2025?",
        required_tools=frozenset({"account_statement_tool"}),
    ),

    # ── fx_rates_tool ─────────────────────────────────────────────────────────
    RoutingCase(
        id="fx_rates",
        investor_id="INV001",
        question="What are the current FX rates used for my portfolio reporting?",
        required_tools=frozenset({"fx_rates_tool"}),
    ),

    # ── investor_profile_tool ─────────────────────────────────────────────────
    RoutingCase(
        id="investor_profile",
        investor_id="INV001",
        question="What does my investor profile say?",
        required_tools=frozenset({"investor_profile_tool"}),
    ),
]

# ── Shared graph ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def graph():
    return build_graph()


# ── Helper ────────────────────────────────────────────────────────────────────

def _called_tools(graph, investor_id: str, question: str) -> list[str]:
    config = {
        "configurable": {
            "thread_id": str(uuid4()),
            "investor_id": investor_id,
        }
    }
    state = asyncio.run(
        graph.ainvoke(
            {"messages": [HumanMessage(content=question)], "investor_id": investor_id},
            config=config,
        )
    )
    return extract_called_tool_names(state["messages"])


# ── Parametrized routing test ─────────────────────────────────────────────────

@pytest.mark.eval
@pytest.mark.parametrize("case", ROUTING_CASES, ids=lambda c: c.id)
def test_tool_routing(graph, case: RoutingCase) -> None:
    """Every tool in required_tools must appear in the agent's call trace."""
    called = _called_tools(graph, case.investor_id, case.question)
    called_set = set(called)

    missing = case.required_tools - called_set

    assert not missing, (
        f"\nCase: {case.id}\n"
        f"Question: {case.question!r}\n"
        f"Required tools: {sorted(case.required_tools)}\n"
        f"Called tools:   {called}\n"
        f"Missing:        {sorted(missing)}"
    )

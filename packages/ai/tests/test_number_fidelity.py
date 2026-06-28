"""
Layer 2 eval: number fidelity.

For each test case the agent is invoked end-to-end (real LLM, real DB).
Every number in the LLM's response must be traceable back to something
a tool returned — no hallucinated figures allowed.

Requirements:
    ANTHROPIC_API_KEY must be set (tests call the live Claude API)
    DATABASE_URL must point at the seeded database
    make up-d must be running

Cost: ~$0.03–$0.05 per test case (Sonnet 4.6 rates).
Run time: ~15–30 s per case (thinking mode + tool calls).

Usage:
    make test-eval                        # all 6 fidelity cases
    make test-eval-k k=down_round         # single case by keyword
"""

import asyncio
import os
from pathlib import Path
from uuid import uuid4

import pytest
from langchain_core.messages import HumanMessage

# ---------------------------------------------------------------------------
# Load .env so ANTHROPIC_API_KEY is available when running locally
# ---------------------------------------------------------------------------

try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).parents[4] / ".env"   # repo root
    if _env_path.exists():
        load_dotenv(_env_path, override=False)
except ImportError:
    pass  # python-dotenv not installed; env vars must be set externally

# ---------------------------------------------------------------------------
# Skip entire module if API key is absent
# ---------------------------------------------------------------------------

if not os.getenv("ANTHROPIC_API_KEY"):
    pytest.skip(
        "ANTHROPIC_API_KEY not set — skipping fidelity evals. "
        "Add it to .env or export it before running.",
        allow_module_level=True,
    )

from ai.agent import build_graph  # noqa: E402  (import after skip check)
from tests.eval_utils import (  # noqa: E402
    check_number_fidelity,
    extract_final_text,
    extract_tool_outputs_from_messages,
)

# ---------------------------------------------------------------------------
# Shared graph instance (built once for all tests)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def graph():
    return build_graph()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _run(graph, investor_id: str, question: str) -> tuple[dict, str]:
    """Invoke the agent synchronously and return (fidelity_result, response_text)."""
    config = {
        "configurable": {
            "thread_id": str(uuid4()),   # fresh thread — no cross-test state
            "investor_id": investor_id,
        }
    }

    state = asyncio.run(
        graph.ainvoke(
            {"messages": [HumanMessage(content=question)], "investor_id": investor_id},
            config=config,
        )
    )

    messages = state["messages"]
    tool_outputs = extract_tool_outputs_from_messages(messages)
    response_text = extract_final_text(messages)

    assert tool_outputs, (
        f"No tool outputs found — agent did not call any tools.\n"
        f"Question: {question}\nResponse: {response_text[:300]}"
    )
    assert response_text, "Agent returned an empty response"

    return check_number_fidelity(response_text, tool_outputs), response_text


# ---------------------------------------------------------------------------
# Fidelity test cases
# ---------------------------------------------------------------------------

@pytest.mark.eval
def test_fidelity_portfolio_moic(graph):
    """
    EC-05 variant: Portfolio-level MOIC, DPI, RVPI for INV001 (GBP reporting).
    All figures must come from portfolio_summary_tool.
    """
    result, response = _run(graph, "INV001", "What is my overall portfolio performance — MOIC, DPI, and RVPI?")

    assert result["pass"], (
        f"Hallucinated numbers: {result['hallucinated']}\n"
        f"Stated numbers: {result['stated']}\n"
        f"Allowed values from tools: {result['allowed_count']} entries\n"
        f"Response:\n{response[:600]}"
    )


@pytest.mark.eval
def test_fidelity_multi_round_position(graph):
    """
    EC-03: Multi-round Forgecraft position (INV001, 3 rounds).
    MOIC per round and aggregate must match position_detail_tool output exactly.
    """
    result, response = _run(graph, "INV001", "How is my Forgecraft Robotics investment performing across all rounds?")

    assert result["pass"], (
        f"Hallucinated numbers: {result['hallucinated']}\n"
        f"Stated: {result['stated']}\n"
        f"Response:\n{response[:600]}"
    )


@pytest.mark.eval
def test_fidelity_down_round(graph):
    """
    EC-09: Down round — Qubrium Series B (INV004).
    Current price 6.20, entry 10.00, multiple 0.62 — must all come from tools.
    """
    result, response = _run(graph, "INV004", "How is my Qubrium Series B position doing?")

    assert result["pass"], (
        f"Hallucinated numbers: {result['hallucinated']}\n"
        f"Stated: {result['stated']}\n"
        f"Response:\n{response[:600]}"
    )


@pytest.mark.eval
def test_fidelity_exited_deal(graph):
    """
    EC-07: Exited deal — Helianthe Energy (INV011).
    MOIC comes from distributions only; current value zero — LLM must not invent a price.

    Known edge case: the LLM occasionally computes the holding period in fractional years
    (e.g. "2.75 years") which is not in the tool output. This is temporal arithmetic —
    a minor design violation. Architectural fix: add holding_period_years to the tool.
    If this test fails with a small decimal (<5) as the only hallucinated value, inspect
    the response for a "years" phrase before treating it as a genuine hallucination.
    """
    result, response = _run(graph, "INV011", "What returns did I receive from Helianthe Energy?")

    assert result["pass"], (
        f"Hallucinated numbers: {result['hallucinated']}\n"
        f"Stated: {result['stated']}\n"
        f"Response:\n{response[:800]}"
    )


@pytest.mark.eval
def test_fidelity_partial_secondary(graph):
    """
    EC-10: Partial secondary — Tallybook (INV013, 30% realised).
    Current value = units × 0.7 × latest_price — must come from position_detail_tool.
    """
    result, response = _run(graph, "INV013", "What is my Tallybook position worth, and how much have I already realised?")

    assert result["pass"], (
        f"Hallucinated numbers: {result['hallucinated']}\n"
        f"Stated: {result['stated']}\n"
        f"Response:\n{response[:600]}"
    )


@pytest.mark.eval
def test_fidelity_upcoming_obligations(graph):
    """
    EC-11: Overdue fees and upcoming obligations (INV001).
    All fee amounts and due dates must come from upcoming_obligations_tool.
    """
    result, response = _run(graph, "INV001", "What are my upcoming capital calls and fees, and do I have anything overdue?")

    assert result["pass"], (
        f"Hallucinated numbers: {result['hallucinated']}\n"
        f"Stated: {result['stated']}\n"
        f"Response:\n{response[:600]}"
    )


@pytest.mark.eval
def test_fidelity_written_off_deal(graph):
    """
    EC-08: Written-off deal — Yappio (INV010).
    Current value = 0 and MOIC = 0 — LLM must not fabricate recovery figures.
    """
    result, response = _run(graph, "INV010", "What happened to my Yappio investment?")

    assert result["pass"], (
        f"Hallucinated numbers: {result['hallucinated']}\n"
        f"Stated: {result['stated']}\n"
        f"Response:\n{response[:600]}"
    )

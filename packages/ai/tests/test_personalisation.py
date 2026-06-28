"""
Layer 5 eval: personalisation compliance — LLM-as-judge.

Tests that the agent's communication style matches the investor's assigned mode:
  simplified — plain English, all jargon explained, warm accessible tone
  standard   — professional language, definitions on first use, clear structure
  expert     — data-dense, VC/PE vocabulary assumed, metric-led, no hand-holding

Tiers:
  Fast (no LLM): verify compute_mode scoring and system-prompt structure markers
  Eval (LLM-as-judge): invoke agent, then ask Claude to score the response against
                        the expected mode's rubric at temperature=0

Judge model: claude-sonnet-4-6 (same as agent), temperature=0 (deterministic).
Pass threshold: judge score >= 7 / 10.

Investor anchors:
  INV016  Isabella Rossi    — Low tech, age 58, 3 deals  → simplified
  INV001  Idris Olawale     — High tech, age 52, 4 deals → standard
  INV002  Selina Voss       — High tech, age 49, 6 deals → expert

Cost: ~3 agent runs × ~$0.07 + ~5 judge calls × ~$0.015 ≈ $0.29 per full run.
"""

import asyncio
import json
import os
import re
from pathlib import Path
from uuid import uuid4

import pytest
from langchain_core.messages import HumanMessage

# ── .env loading ──────────────────────────────────────────────────────────────

try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).parents[4] / ".env"
    if _env_path.exists():
        load_dotenv(_env_path, override=False)
except ImportError:
    pass

# ── Imports ───────────────────────────────────────────────────────────────────

from common.database import SessionLocal
from ai.personalisation import compute_mode
from ai.prompts import build_system_prompt
from ai.tools import get_investor_profile
from tests.eval_utils import extract_final_text

# ── Investor anchors ──────────────────────────────────────────────────────────

SIMPLIFIED_INVESTOR = "INV016"  # Isabella Rossi  — Low, age 58, 3 deals
STANDARD_INVESTOR   = "INV001"  # Idris Olawale   — High, age 52, 4 deals
EXPERT_INVESTOR     = "INV002"  # Selina Voss     — High, age 49, 6 deals

# ── Rubrics ───────────────────────────────────────────────────────────────────

_SIMPLIFIED_RUBRIC = """
SIMPLIFIED mode requires ALL of the following:
1. Uses plain, everyday English — avoids unexplained financial or VC jargon
2. Any technical term (e.g. MOIC, DPI, RVPI, carry, SPV, IRR) MUST be explained in
   parentheses on first use: e.g. "MOIC (how many times your money has grown)"
3. Leads with the bottom line in plain language ("your investments are worth X")
   rather than metrics-first ("MOIC is X")
4. Concrete, relatable language: "you earned £X back" rather than "realised DPI of 1.5×"
5. Warm, accessible tone — not condescending, but written for a non-finance expert
"""

_STANDARD_RUBRIC = """
STANDARD mode requires ALL of the following:
1. Clear, professional language — neither overly simplified nor overly technical
2. Defines non-everyday terms (MOIC, DPI, carry) on first use; assumes basic finance literacy
3. Structured with a headline figure followed by a brief breakdown
4. Does not patronise with overly basic explanations
"""

_EXPERT_RUBRIC = """
EXPERT mode requires ALL of the following:
1. Concise and data-dense — no unnecessary padding or simplifications
2. Uses standard VC/PE vocabulary WITHOUT defining it:
   MOIC, DPI, RVPI, carry, NAV, IRR, SPV, SAFE, unrealised/realised — all used freely
3. Leads with key metrics (multiples, rates, figures) rather than prose descriptions
4. Does NOT explain what MOIC, DPI, RVPI etc. mean — the investor already knows
5. Professional, efficient tone — no hand-holding, no filler sentences
"""

RUBRICS: dict[str, str] = {
    "simplified": _SIMPLIFIED_RUBRIC,
    "standard": _STANDARD_RUBRIC,
    "expert": _EXPERT_RUBRIC,
}

JUDGE_MODEL = "claude-sonnet-4-6"
PASS_THRESHOLD = 7   # score out of 10

OVERVIEW_QUESTION = "Give me an overview of my portfolio performance."
FEE_QUESTION = "What management fees and performance fees am I paying?"

# ═════════════════════════════════════════════════════════════════════════════
# Fast tests — no LLM
# ═════════════════════════════════════════════════════════════════════════════

def test_personalisation_mode_scoring():
    """
    compute_mode returns the correct mode for known investor profiles.
    These are the three investors used in the eval tests — if the modes change
    (e.g. because seed data was updated), the eval tests would need re-anchoring.
    """
    db = SessionLocal()
    try:
        cases = [
            (SIMPLIFIED_INVESTOR, "simplified"),
            (STANDARD_INVESTOR,   "standard"),
            (EXPERT_INVESTOR,     "expert"),
        ]
        for inv_id, expected_mode in cases:
            profile = get_investor_profile(inv_id, db)
            actual = compute_mode(profile)
            assert actual == expected_mode, (
                f"Investor {inv_id} ({profile['investor_name']}) expected mode={expected_mode}, "
                f"got mode={actual}. "
                f"tech={profile['tech_savviness']} "
                f"age={profile['age']} deals={profile['deal_count']}"
            )
    finally:
        db.close()


def test_personalisation_system_prompt_contains_mode_markers():
    """
    build_system_prompt injects mode-specific language that steers the LLM's style.
    Simplified prompt must mention 'plain English'. Expert prompt must mention 'data-dense'.
    Both must include the fixed section ('IMPORTANT RULES').
    """
    db = SessionLocal()
    try:
        cases = [
            (SIMPLIFIED_INVESTOR, "simplified", "plain English"),
            (EXPERT_INVESTOR,     "expert",     "data-dense"),
        ]
        for inv_id, expected_mode, expected_marker in cases:
            profile = get_investor_profile(inv_id, db)
            mode = compute_mode(profile)
            assert mode == expected_mode

            prompt = build_system_prompt(profile, mode)

            assert "IMPORTANT RULES" in prompt, (
                f"System prompt for {expected_mode} mode is missing the fixed rules section."
            )
            assert expected_marker.lower() in prompt.lower(), (
                f"System prompt for {expected_mode} mode is missing marker '{expected_marker}'.\n"
                f"Prompt excerpt (first 400 chars):\n{prompt[:400]}"
            )
    finally:
        db.close()


# ═════════════════════════════════════════════════════════════════════════════
# Shared fixtures for eval tests
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def graph():
    """Build and return the agent graph; skip all eval tests if no API key."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set — skipping personalisation eval tests")
    from ai.agent import build_graph
    return build_graph()


def _invoke(graph, investor_id: str, question: str) -> str:
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
    return extract_final_text(state["messages"])


@pytest.fixture(scope="module")
def simplified_overview(graph) -> str:
    """Cached response: SIMPLIFIED_INVESTOR × OVERVIEW_QUESTION."""
    return _invoke(graph, SIMPLIFIED_INVESTOR, OVERVIEW_QUESTION)


@pytest.fixture(scope="module")
def expert_overview(graph) -> str:
    """Cached response: EXPERT_INVESTOR × OVERVIEW_QUESTION."""
    return _invoke(graph, EXPERT_INVESTOR, OVERVIEW_QUESTION)


# ── Judge helper ──────────────────────────────────────────────────────────────

def _judge(response_text: str, investor_id: str, rubric_mode: str) -> dict:
    """
    Ask Claude to score response_text against rubric_mode's criteria.

    Uses temperature=0 for determinism. Returns:
    {
        "pass": bool,
        "score": int (0–10),
        "violations": list[str],
        "reasoning": str
    }
    """
    import anthropic

    db = SessionLocal()
    try:
        profile = get_investor_profile(investor_id, db)
    finally:
        db.close()

    age_str = str(profile.get("age") or "N/A (institutional)")
    rubric = RUBRICS[rubric_mode]

    prompt = f"""You are evaluating whether a financial assistant's response is appropriately styled for the investor's assigned communication mode.

INVESTOR PROFILE:
- Name: {profile['investor_name']}
- Type: {profile['investor_type']}
- Tech savviness: {profile['tech_savviness']}
- Age: {age_str}
- Active deals: {profile['deal_count']}
- Assigned communication mode: {rubric_mode.upper()}

EXPECTED STYLE FOR {rubric_mode.upper()} MODE:
{rubric}

RESPONSE TO EVALUATE:
---
{response_text}
---

Assess whether the response's communication STYLE matches the {rubric_mode.upper()} mode requirements.
Focus ONLY on writing style and vocabulary — ignore whether the financial figures are correct.

Respond with ONLY a valid JSON object (no surrounding text, no code fences):
{{
  "pass": <true if the response clearly matches the mode's style, false otherwise>,
  "score": <integer 0–10; 10 = perfectly matches all mode criteria>,
  "violations": [<list of specific style violations found; empty list if none>],
  "reasoning": "<1–2 sentences explaining your verdict>"
}}"""

    client = anthropic.Anthropic()
    message = client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=512,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = message.content[0].text.strip()

    # Extract JSON even if wrapped in a code fence
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    parsed = json.loads(match.group() if match else raw)

    # Normalise: derive boolean pass from score if judge omitted it
    if "pass" not in parsed:
        parsed["pass"] = int(parsed.get("score", 0)) >= PASS_THRESHOLD

    return parsed


# ═════════════════════════════════════════════════════════════════════════════
# Eval tests
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.eval
def test_personalisation_simplified_plain_language(simplified_overview):
    """
    A simplified-mode investor's overview response must use plain language.
    Technical terms must be explained; tone must be accessible and warm.
    """
    result = _judge(simplified_overview, SIMPLIFIED_INVESTOR, "simplified")

    assert result["pass"] and int(result["score"]) >= PASS_THRESHOLD, (
        f"Simplified investor response failed style evaluation.\n"
        f"Score: {result['score']}/10\n"
        f"Violations: {result.get('violations', [])}\n"
        f"Reasoning: {result.get('reasoning', '')}\n"
        f"Response (first 700 chars):\n{simplified_overview[:700]}"
    )


@pytest.mark.eval
def test_personalisation_expert_technical_density(expert_overview):
    """
    An expert-mode investor's overview response must be data-dense.
    Standard VC/PE vocabulary must be used without definitions.
    """
    result = _judge(expert_overview, EXPERT_INVESTOR, "expert")

    assert result["pass"] and int(result["score"]) >= PASS_THRESHOLD, (
        f"Expert investor response failed style evaluation.\n"
        f"Score: {result['score']}/10\n"
        f"Violations: {result.get('violations', [])}\n"
        f"Reasoning: {result.get('reasoning', '')}\n"
        f"Response (first 700 chars):\n{expert_overview[:700]}"
    )


@pytest.mark.eval
def test_personalisation_simplified_no_unexplained_jargon(graph):
    """
    Fee question is likely to surface VC terms (management fee, carry, hurdle, performance fee).
    In simplified mode, every such term must be explained in plain language on first use.
    """
    response = _invoke(graph, SIMPLIFIED_INVESTOR, FEE_QUESTION)
    result = _judge(response, SIMPLIFIED_INVESTOR, "simplified")

    assert result["pass"] and int(result["score"]) >= PASS_THRESHOLD, (
        f"Fee response for simplified investor contains unexplained jargon.\n"
        f"Score: {result['score']}/10\n"
        f"Violations: {result.get('violations', [])}\n"
        f"Reasoning: {result.get('reasoning', '')}\n"
        f"Response (first 700 chars):\n{response[:700]}"
    )


@pytest.mark.eval
def test_personalisation_style_contrast(simplified_overview, expert_overview):
    """
    The same question asked by a simplified and an expert investor produces
    genuinely different responses:

    1. Simplified response passes simplified rubric ✓  (also verified in test above)
    2. Expert response passes expert rubric ✓           (also verified in test above)
    3. Simplified response FAILS expert rubric          (too plain/explanatory for expert)

    Check 3 is the discriminating assertion: if the simplified response unexpectedly
    passes the expert rubric, the two modes are not producing meaningfully different output.
    """
    # 1. Simplified passes simplified
    r_s_as_s = _judge(simplified_overview, SIMPLIFIED_INVESTOR, "simplified")
    assert r_s_as_s["pass"] and int(r_s_as_s["score"]) >= PASS_THRESHOLD, (
        f"Contrast test: simplified response did not pass simplified rubric.\n"
        f"Score: {r_s_as_s['score']}/10  Violations: {r_s_as_s.get('violations', [])}"
    )

    # 2. Expert passes expert
    r_e_as_e = _judge(expert_overview, EXPERT_INVESTOR, "expert")
    assert r_e_as_e["pass"] and int(r_e_as_e["score"]) >= PASS_THRESHOLD, (
        f"Contrast test: expert response did not pass expert rubric.\n"
        f"Score: {r_e_as_e['score']}/10  Violations: {r_e_as_e.get('violations', [])}"
    )

    # 3. Simplified FAILS expert rubric  ← the contrast check
    r_s_as_e = _judge(simplified_overview, SIMPLIFIED_INVESTOR, "expert")
    assert not r_s_as_e["pass"] or int(r_s_as_e["score"]) < PASS_THRESHOLD, (
        f"Contrast test: simplified investor response unexpectedly PASSED the expert rubric.\n"
        f"This suggests both modes produce similar output — personalisation may not be working.\n"
        f"Score against expert rubric: {r_s_as_e['score']}/10\n"
        f"Reasoning: {r_s_as_e.get('reasoning', '')}\n"
        f"Simplified response:\n{simplified_overview[:500]}"
    )

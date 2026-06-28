"""
Utilities for number fidelity evaluation.

Core idea: every financial figure in an LLM response must be traceable back to
something a tool returned. These helpers extract the allowed set from tool outputs
and the stated set from response text, then compute the diff.
"""

import json
import re


# ── Number extraction from tool outputs ──────────────────────────────────────

def _allowed_values(tool_outputs: list[dict]) -> set[float]:
    """
    Build the complete set of numeric values the LLM is permitted to state.

    For each value v found in the tool output:
    - Add v itself
    - Add v rounded to 0–4 decimal places (covers LLM rounding prose like "1.84×")
    - For 0 < v < 1 (fractional), also add v×100 and its rounds (covers "30%" for 0.3)
    """
    allowed: set[float] = set()

    def traverse(obj: object) -> None:
        if isinstance(obj, bool):
            return
        if isinstance(obj, (int, float)):
            v = float(obj)
            if v == 0.0:
                return
            allowed.add(v)
            for dp in range(5):
                allowed.add(round(v, dp))
            if 0.0 < abs(v) <= 1.0:
                # Cover percentage expressions (0.3 → "30%", 1.0 → "100%")
                pct = v * 100
                allowed.add(pct)
                for dp in range(5):
                    allowed.add(round(pct, dp))
        elif isinstance(obj, dict):
            for val in obj.values():
                traverse(val)
        elif isinstance(obj, list):
            for item in obj:
                traverse(item)

    for output in tool_outputs:
        traverse(output)

    return allowed


# ── Number extraction from response text ─────────────────────────────────────

_YEAR_RE = re.compile(r'\b(19|20)\d{2}\b')
# Matches: 1,234,567.89 | 1234.56 | 42000 | 1.84 | 0.62
_NUMBER_RE = re.compile(r'\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b|\b\d+\.\d+\b')


def _stated_numbers(text: str) -> set[float]:
    """
    Extract financial numbers from LLM response text.

    Filtering rules:
    - Strip years (20xx / 19xx) — date references are not financial figures
    - Skip integers < 100 — likely structural language ("3 rounds", "14 distributions",
      "18%" written as a plain integer) rather than specific financial amounts
    - Skip zero
    """
    clean = _YEAR_RE.sub('YEAR', text)
    stated: set[float] = set()
    for m in _NUMBER_RE.finditer(clean):
        raw = m.group().replace(',', '')
        try:
            v = float(raw)
        except ValueError:
            continue
        if v == 0.0:
            continue
        if v == int(v) and v < 100:      # small integer — skip
            continue
        stated.add(v)
    return stated


# ── Fidelity check ────────────────────────────────────────────────────────────

def _close_enough(stated: float, allowed: float) -> bool:
    """True if stated is within ±2% (or ±0.01 absolute for tiny values) of allowed."""
    diff = abs(stated - allowed)
    if abs(allowed) < 0.5:
        return diff <= 0.01
    return diff / abs(allowed) <= 0.02


def _is_arithmetic_derivation(stated: float, allowed: set[float]) -> bool:
    """
    True if stated can be derived through one or two arithmetic steps on tool-output values.

    Step 1 — direct derivations from tool outputs:
      a) |A − B| and A + B for any two significant amounts (> 500)
      b) A × f and A × (1 − f) for any priceable value (> 0.5) and fraction (0 < f ≤ 1)

    Step 2 — one level of expansion:
      Build an intermediate set of all step-1 products, then re-run the sum/diff check
      against the union of original + intermediate values.
      This handles two-step computations such as:
        profit_on_sold = gross_proceeds − (units × realised_fraction × entry_price)
        e.g. 8820 = 15120 − (21000 × 0.3) where 6300 is itself a product derivation.

    Note: the architecture requires Python (tools) to do maths, not the LLM.
    This check keeps the eval tolerant of correctly-computed derivations while
    still catching figures that have no connection to any tool output.
    """
    significant = [a for a in allowed if a > 500]
    priceable = [a for a in allowed if a > 0.5]
    fractional = [f for f in allowed if 0.0 < f <= 1.0]

    # Step 1a: sum/diff of significant tool-output values
    for i, a in enumerate(significant):
        for b in significant[i:]:
            diff = abs(a - b)
            if diff > 0 and _close_enough(stated, diff):
                return True
            if _close_enough(stated, a + b):
                return True

    # Step 1b: product with fraction (covers remaining_units, entry_cost_of_tranche, etc.)
    intermediate: set[float] = set()
    for a in priceable:
        for f in fractional:
            v = a * f
            if v > 0:
                intermediate.add(v)
            c = a * (1.0 - f)
            if c > 0:
                intermediate.add(c)
            if _close_enough(stated, v) or _close_enough(stated, c if c > 0 else -1):
                return True

    # Step 2: sum/diff against the union of original + intermediate values
    expanded = [x for x in (set(significant) | intermediate) if x > 500]
    for i, a in enumerate(expanded):
        for b in expanded[i:]:
            diff = abs(a - b)
            if diff > 0 and _close_enough(stated, diff):
                return True
            if _close_enough(stated, a + b):
                return True

    return False


def check_number_fidelity(response_text: str, tool_outputs: list[dict]) -> dict:
    """
    Verify that every financial number in response_text is traceable to tool outputs.

    A number "passes" if it:
    - appears directly in tool output (within ±2% rounding tolerance), OR
    - is the difference or sum of two significant amounts from tool output
      (e.g. LLM states unrealised_loss = cost_basis − current_value)

    Returns:
        {
            "pass":         bool   — True if no hallucinated numbers detected
            "stated":       list   — all numbers extracted from the response
            "hallucinated": list   — numbers not traceable to any tool output
            "allowed_count": int   — size of the allowed value set (for debugging)
        }
    """
    allowed = _allowed_values(tool_outputs)
    stated = _stated_numbers(response_text)

    hallucinated = {
        n for n in stated
        if not any(_close_enough(n, a) for a in allowed)
        and not _is_arithmetic_derivation(n, allowed)
    }

    return {
        "pass": len(hallucinated) == 0,
        "stated": sorted(stated),
        "hallucinated": sorted(hallucinated),
        "allowed_count": len(allowed),
    }


# ── Message extraction helpers ────────────────────────────────────────────────

def extract_called_tool_names(messages: list) -> list[str]:
    """Return the ordered list of tool names called during an agent run."""
    from langchain_core.messages import AIMessage

    names: list[str] = []
    for msg in messages:
        if isinstance(msg, AIMessage):
            for tc in msg.tool_calls or []:
                names.append(tc["name"])
    return names


def extract_tool_outputs_from_messages(messages: list) -> list[dict]:
    """Parse all ToolMessage JSON payloads from a completed graph run."""
    from langchain_core.messages import ToolMessage

    outputs = []
    for msg in messages:
        if isinstance(msg, ToolMessage):
            try:
                outputs.append(json.loads(msg.content))
            except (json.JSONDecodeError, TypeError, AttributeError):
                pass
    return outputs


def extract_final_text(messages: list) -> str:
    """Return the text content of the last AIMessage in the message list."""
    from langchain_core.messages import AIMessage

    for msg in reversed(messages):
        if not isinstance(msg, AIMessage):
            continue
        content = msg.content
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = [
                b["text"]
                for b in content
                if isinstance(b, dict) and b.get("type") == "text" and b.get("text")
            ]
            if parts:
                return " ".join(parts)
    return ""

import json
import os

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from common.database import SessionLocal
from ai.personalisation import compute_mode
from ai.prompts import build_system_prompt
from ai.state import AgentState
from ai.tools import (
    get_account_statement,
    get_distributions,
    get_fee_detail,
    get_fx_rates,
    get_investor_profile,
    get_portfolio_summary,
    get_position_detail,
    get_upcoming_obligations,
    get_valuation_history,
    search_company,
)

# ---------------------------------------------------------------------------
# LangChain tool wrappers
# Each wrapper hides investor_id (read from RunnableConfig) and the DB session
# from the LLM. Only the business-logic parameters are exposed in the schema.
# ---------------------------------------------------------------------------

def _investor_id(config: RunnableConfig) -> str:
    return config["configurable"]["investor_id"]


@tool
def portfolio_summary_tool(config: RunnableConfig) -> str:
    """Get a complete summary of the investor's portfolio: all positions, total committed and contributed capital, current value, MOIC, DPI, RVPI, and FX-converted totals in the investor's reporting currency."""
    db = SessionLocal()
    try:
        return json.dumps(get_portfolio_summary(_investor_id(config), db))
    finally:
        db.close()


@tool
def position_detail_tool(company_name: str, config: RunnableConfig) -> str:
    """Get a detailed breakdown for a specific portfolio company: per-round cost basis, units, current value, valuation history, and distributions. Call search_company_tool first if the exact name is uncertain."""
    db = SessionLocal()
    try:
        return json.dumps(get_position_detail(_investor_id(config), db, company_name))
    finally:
        db.close()


@tool
def upcoming_obligations_tool(config: RunnableConfig) -> str:
    """Get all upcoming and overdue capital calls and fees for the investor, with due dates and amounts in both deal currency and reporting currency."""
    db = SessionLocal()
    try:
        return json.dumps(get_upcoming_obligations(_investor_id(config), db))
    finally:
        db.close()


@tool
def distributions_tool(company_name: str | None = None, *, config: RunnableConfig) -> str:
    """Get distributions received by the investor. Optionally filter by company name. Returns gross amount, performance fee withheld, and net amount per distribution."""
    db = SessionLocal()
    try:
        return json.dumps(get_distributions(_investor_id(config), db, company_name))
    finally:
        db.close()


@tool
def fee_detail_tool(company_name: str | None = None, *, config: RunnableConfig) -> str:
    """Get fee details for the investor's deals: standard rates from the deal versus the investor's effective (possibly discounted) rates, plus paid, upcoming, and overdue amounts. Optionally filter by company name."""
    db = SessionLocal()
    try:
        return json.dumps(get_fee_detail(_investor_id(config), db, company_name))
    finally:
        db.close()


@tool
def valuation_history_tool(company_name: str, config: RunnableConfig) -> str:
    """Get the full valuation mark history for a portfolio company: all dates, share prices, multiples vs entry, and mark sources."""
    db = SessionLocal()
    try:
        return json.dumps(get_valuation_history(_investor_id(config), db, company_name))
    finally:
        db.close()


@tool
def account_statement_tool(
    start_date: str | None = None,
    end_date: str | None = None,
    *,
    config: RunnableConfig,
) -> str:
    """Get the investor's signed cashflow ledger (contributions negative, distributions and proceeds positive). Optionally filter by start_date and end_date in YYYY-MM-DD format."""
    db = SessionLocal()
    try:
        return json.dumps(get_account_statement(_investor_id(config), db, start_date, end_date))
    finally:
        db.close()


@tool
def fx_rates_tool(config: RunnableConfig) -> str:
    """Get current FX rates for USD, GBP, EUR, and AED as of the report date."""
    db = SessionLocal()
    try:
        return json.dumps(get_fx_rates(db))
    finally:
        db.close()


@tool
def search_company_tool(name_query: str, config: RunnableConfig) -> str:
    """Search for portfolio companies by partial name. Use this to resolve ambiguous names before calling other tools. Returns all matching companies with their IDs and sectors."""
    db = SessionLocal()
    try:
        return json.dumps(search_company(db, name_query))
    finally:
        db.close()


@tool
def investor_profile_tool(config: RunnableConfig) -> str:
    """Get the investor's own profile: name, type, country, reporting currency, age, tech savviness, KYC status, and top sectors."""
    db = SessionLocal()
    try:
        return json.dumps(get_investor_profile(_investor_id(config), db))
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------

_ALL_TOOLS = [
    portfolio_summary_tool,
    position_detail_tool,
    upcoming_obligations_tool,
    distributions_tool,
    fee_detail_tool,
    valuation_history_tool,
    account_statement_tool,
    fx_rates_tool,
    search_company_tool,
    investor_profile_tool,
]


def _build_llm():
    return ChatAnthropic(
        model="claude-sonnet-4-6",
        max_tokens=8096,
        thinking={"type": "adaptive", "display": "summarized"},
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
    ).bind_tools(_ALL_TOOLS)


def build_context_node(state: AgentState) -> dict:
    # No-op on subsequent turns — profile is already in state (restored by MemorySaver)
    if state.get("investor_profile"):
        return {}

    investor_id = state["investor_id"]
    db = SessionLocal()
    try:
        profile = get_investor_profile(investor_id, db)
        mode = compute_mode(profile)
        prompt = build_system_prompt(profile, mode)
    finally:
        db.close()

    return {
        "investor_profile": profile,
        "personalization_mode": mode,
        "system_prompt": prompt,
    }


def agent_node(state: AgentState, llm_with_tools) -> dict:
    system_msg = SystemMessage(content=state["system_prompt"])
    response = llm_with_tools.invoke([system_msg] + list(state["messages"]))
    return {"messages": [response]}


def should_continue(state: AgentState) -> str:
    last = state["messages"][-1]
    if getattr(last, "tool_calls", None):
        return "tools"
    return END


# ---------------------------------------------------------------------------
# Graph factory — call once at startup, reuse across requests
# ---------------------------------------------------------------------------

def build_graph():
    llm_with_tools = _build_llm()

    def _agent_node(state: AgentState) -> dict:
        return agent_node(state, llm_with_tools)

    tool_node = ToolNode(_ALL_TOOLS)

    graph = StateGraph(AgentState)
    graph.add_node("build_context", build_context_node)
    graph.add_node("agent", _agent_node)
    graph.add_node("tools", tool_node)

    graph.set_entry_point("build_context")
    graph.add_edge("build_context", "agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    return graph.compile(checkpointer=MemorySaver())

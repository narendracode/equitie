import asyncio
import json
import time
import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel
from sqlalchemy.orm import Session

from common.database import get_db
from common.models import Investor
from api.services.chat_service import (
    complete_agent_run,
    create_agent_run,
    create_session,
    fail_agent_run,
    get_investors_for_dropdown,
    get_messages,
    get_session,
    save_message,
)
from api.services.langsmith_service import record_run_cost

logger = logging.getLogger(__name__)

router = APIRouter()

# Graph is built once at module load — shared across all requests
_graph = None


def _get_graph():
    global _graph
    if _graph is None:
        from ai.agent import build_graph
        _graph = build_graph()
    return _graph


# Human-readable labels for each tool shown during streaming
_TOOL_LABELS: dict[str, str] = {
    "portfolio_summary_tool":    "Fetching your portfolio overview…",
    "position_detail_tool":      "Looking up your position…",
    "upcoming_obligations_tool": "Checking upcoming obligations…",
    "distributions_tool":        "Fetching your distributions…",
    "fee_detail_tool":           "Looking up fee details…",
    "valuation_history_tool":    "Fetching valuation history…",
    "account_statement_tool":    "Loading your account statement…",
    "fx_rates_tool":             "Fetching FX rates…",
    "search_company_tool":       "Searching for company…",
    "investor_profile_tool":     "Loading your profile…",
}


def _tool_label(tool_name: str) -> str:
    return _TOOL_LABELS.get(tool_name, f"Running {tool_name}…")


# -----------------------------------------------------------------------
# GET /chat/investors
# -----------------------------------------------------------------------

@router.get("/investors")
def list_investors(db: Session = Depends(get_db)):
    return get_investors_for_dropdown(db)


# -----------------------------------------------------------------------
# POST /chat/sessions
# -----------------------------------------------------------------------

class CreateSessionRequest(BaseModel):
    investor_id: str


@router.post("/sessions")
def create_chat_session(body: CreateSessionRequest, db: Session = Depends(get_db)):
    investor = db.get(Investor, body.investor_id)
    if not investor:
        raise HTTPException(status_code=404, detail="Investor not found")

    session = create_session(body.investor_id, db)
    return {
        "session_id": str(session.session_id),
        "investor_id": investor.investor_id,
        "investor_name": investor.investor_name,
        "reporting_currency": investor.reporting_currency,
    }


# -----------------------------------------------------------------------
# GET /chat/{session_id}/stream   (SSE)
# -----------------------------------------------------------------------

async def _fetch_cost_background(run_id_str: str) -> None:
    """Run LangSmith cost fetch in a thread so it never blocks the event loop."""
    await asyncio.sleep(8)  # give LangSmith time to process the completed run
    await asyncio.to_thread(record_run_cost, run_id_str)


@router.get("/{session_id}/stream")
async def stream_chat(
    session_id: uuid.UUID,
    message: str,
    db: Session = Depends(get_db),
):
    session = get_session(session_id, db)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    investor_id = session.investor_id
    graph = _get_graph()

    async def generate():
        run_id: uuid.UUID | None = None
        run_id_str: str | None = None
        thinking_parts: list[str] = []
        token_parts: list[str] = []
        start_time = time.time()

        # 1. Persist the user message
        user_msg = save_message(session_id, "user", message, db)

        config = {
            "configurable": {
                "thread_id": str(session_id),
                "investor_id": investor_id,
            }
        }
        input_state = {
            "investor_id": investor_id,
            "messages": [HumanMessage(message)],
        }

        try:
            async for event in graph.astream_events(input_state, config=config, version="v2"):
                # Capture run_id from first event that carries it
                if run_id is None and event.get("run_id"):
                    run_id = uuid.UUID(str(event["run_id"]))
                    run_id_str = str(run_id)
                    create_agent_run(session_id, user_msg.message_id, run_id, db)

                kind = event["event"]

                if kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and isinstance(chunk.content, list):
                        for block in chunk.content:
                            if not isinstance(block, dict):
                                continue
                            btype = block.get("type")
                            if btype == "thinking" and "thinking" in block:
                                thinking_parts.append(block["thinking"])
                                yield f'data: {json.dumps({"type": "thinking_delta", "content": block["thinking"]})}\n\n'
                            elif btype == "text" and "text" in block:
                                token_parts.append(block["text"])
                                yield f'data: {json.dumps({"type": "token", "content": block["text"]})}\n\n'

                elif kind == "on_tool_start":
                    tool_name = event.get("name", "")
                    yield f'data: {json.dumps({"type": "tool_start", "tool": tool_name, "label": _tool_label(tool_name)})}\n\n'

                elif kind == "on_tool_end":
                    tool_name = event.get("name", "")
                    yield f'data: {json.dumps({"type": "tool_end", "tool": tool_name})}\n\n'

        except Exception as exc:
            logger.exception("Agent error for session %s", session_id)
            if run_id:
                fail_agent_run(run_id, db)
            yield f'data: {json.dumps({"type": "error", "content": str(exc)})}\n\n'
            return

        # 2. Persist the completed assistant message
        duration_ms = int((time.time() - start_time) * 1000)
        answer = "".join(token_parts)
        thinking = "".join(thinking_parts) or None

        asst_msg = save_message(
            session_id, "assistant", answer, db, thinking_content=thinking
        )

        if run_id:
            complete_agent_run(run_id, asst_msg.message_id, duration_ms, db)
            asyncio.create_task(_fetch_cost_background(run_id_str))

        yield f'data: {json.dumps({"type": "done"})}\n\n'

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )


# -----------------------------------------------------------------------
# GET /chat/{session_id}/messages
# -----------------------------------------------------------------------

@router.get("/{session_id}/messages")
def get_chat_messages(session_id: uuid.UUID, db: Session = Depends(get_db)):
    session = get_session(session_id, db)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = get_messages(session_id, db)
    return {
        "session_id": str(session_id),
        "investor_id": session.investor_id,
        "messages": [
            {
                "message_id": str(m.message_id),
                "role": m.role,
                "content": m.content,
                "thinking_content": m.thinking_content,
                "tool_name": m.tool_name,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
    }

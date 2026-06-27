import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from common.models import ChatSession, ChatMessage, AgentRun, Investor


def get_investors_for_dropdown(db: Session) -> list[dict]:
    rows = db.execute(
        select(Investor).order_by(Investor.investor_name)
    ).scalars().all()
    return [
        {
            "investor_id": inv.investor_id,
            "investor_name": inv.investor_name,
            "reporting_currency": inv.reporting_currency,
        }
        for inv in rows
    ]


def create_session(investor_id: str, db: Session) -> ChatSession:
    session = ChatSession(investor_id=investor_id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session(session_id: uuid.UUID, db: Session) -> ChatSession | None:
    return db.get(ChatSession, session_id)


def save_message(
    session_id: uuid.UUID,
    role: str,
    content: str,
    db: Session,
    *,
    thinking_content: str | None = None,
    tool_name: str | None = None,
) -> ChatMessage:
    msg = ChatMessage(
        session_id=session_id,
        role=role,
        content=content,
        thinking_content=thinking_content,
        tool_name=tool_name,
    )
    db.add(msg)
    # keep last_active fresh on every message
    session = db.get(ChatSession, session_id)
    if session:
        session.last_active = datetime.now(timezone.utc)
    db.commit()
    db.refresh(msg)
    return msg


def create_agent_run(
    session_id: uuid.UUID,
    user_message_id: uuid.UUID,
    run_id: uuid.UUID,
    db: Session,
) -> AgentRun:
    agent_run = AgentRun(
        run_id=run_id,
        session_id=session_id,
        user_message_id=user_message_id,
        trace_url=f"https://smith.langchain.com/public/{run_id}/r",
        model_name="claude-sonnet-4-6",
        status="running",
    )
    db.add(agent_run)
    db.commit()
    return agent_run


def complete_agent_run(
    run_id: uuid.UUID,
    assistant_message_id: uuid.UUID,
    duration_ms: int,
    db: Session,
) -> None:
    agent_run = db.get(AgentRun, run_id)
    if agent_run:
        agent_run.status = "completed"
        agent_run.assistant_message_id = assistant_message_id
        agent_run.duration_ms = duration_ms
        agent_run.completed_at = datetime.now(timezone.utc)
        db.commit()


def fail_agent_run(run_id: uuid.UUID, db: Session) -> None:
    agent_run = db.get(AgentRun, run_id)
    if agent_run:
        agent_run.status = "error"
        agent_run.completed_at = datetime.now(timezone.utc)
        db.commit()


def get_messages(session_id: uuid.UUID, db: Session) -> list[ChatMessage]:
    return (
        db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at)
        )
        .scalars()
        .all()
    )

import uuid
from decimal import Decimal
from datetime import datetime
from sqlalchemy import String, Text, Numeric, Integer, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from common.database import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    investor_id: Mapped[str] = mapped_column(String(20), ForeignKey("investors.investor_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_active: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    messages: Mapped[list["ChatMessage"]] = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")
    agent_runs: Mapped[list["AgentRun"]] = relationship("AgentRun", back_populates="session", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<ChatSession {self.session_id} inv={self.investor_id}>"


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    message_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chat_sessions.session_id"))
    role: Mapped[str] = mapped_column(String(20))  # user | assistant | tool
    content: Mapped[str] = mapped_column(Text)
    thinking_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped["ChatSession"] = relationship("ChatSession", back_populates="messages")

    def __repr__(self) -> str:
        return f"<ChatMessage {self.message_id} role={self.role}>"


class AgentRun(Base):
    __tablename__ = "agent_runs"

    # run_id comes from LangSmith — not auto-generated, set by the API layer
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chat_sessions.session_id"))
    user_message_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chat_messages.message_id"))
    assistant_message_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("chat_messages.message_id"), nullable=True)
    trace_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    model_name: Mapped[str] = mapped_column(String(50))
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="running")  # running | completed | error
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    session: Mapped["ChatSession"] = relationship("ChatSession", back_populates="agent_runs")

    def __repr__(self) -> str:
        return f"<AgentRun {self.run_id} status={self.status}>"

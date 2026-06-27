"""chat tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-27

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        sa.Column("session_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("investor_id", sa.String(20), sa.ForeignKey("investors.investor_id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_active", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "chat_messages",
        sa.Column("message_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("chat_sessions.session_id"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("thinking_content", sa.Text, nullable=True),
        sa.Column("tool_name", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "agent_runs",
        sa.Column("run_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("chat_sessions.session_id"), nullable=False),
        sa.Column("user_message_id", UUID(as_uuid=True), sa.ForeignKey("chat_messages.message_id"), nullable=False),
        sa.Column("assistant_message_id", UUID(as_uuid=True), sa.ForeignKey("chat_messages.message_id"), nullable=True),
        sa.Column("trace_url", sa.String(500), nullable=True),
        sa.Column("model_name", sa.String(50), nullable=False),
        sa.Column("prompt_tokens", sa.Integer, nullable=True),
        sa.Column("completion_tokens", sa.Integer, nullable=True),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index("ix_chat_sessions_investor_id", "chat_sessions", ["investor_id"])
    op.create_index("ix_chat_messages_session_id", "chat_messages", ["session_id"])
    op.create_index("ix_chat_messages_created_at", "chat_messages", ["created_at"])
    op.create_index("ix_agent_runs_session_id", "agent_runs", ["session_id"])
    op.create_index("ix_agent_runs_user_message_id", "agent_runs", ["user_message_id"])


def downgrade() -> None:
    op.drop_table("agent_runs")
    op.drop_table("chat_messages")
    op.drop_table("chat_sessions")

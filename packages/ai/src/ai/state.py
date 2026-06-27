from typing import Annotated, NotRequired, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    # Locked at session creation — never mutated after that
    investor_id: str

    # Populated once by build_context node; persisted across turns by MemorySaver
    investor_profile: NotRequired[dict]
    personalization_mode: NotRequired[str]   # simplified | standard | expert
    system_prompt: NotRequired[str]

    # Full conversation history; add_messages reducer appends rather than replaces
    messages: Annotated[list[BaseMessage], add_messages]

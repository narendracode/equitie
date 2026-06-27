import uuid
import logging

from sqlalchemy.orm import Session

from common.database import SessionLocal
from common.models import AgentRun

logger = logging.getLogger(__name__)

# Sonnet 4.6 pricing as of report date
_INPUT_COST_PER_TOKEN = 3 / 1_000_000    # $3 / 1M input tokens
_OUTPUT_COST_PER_TOKEN = 15 / 1_000_000  # $15 / 1M output tokens (includes thinking tokens)


def _update_agent_run_cost(
    run_id: uuid.UUID,
    prompt_tokens: int,
    completion_tokens: int,
    cost_usd: float,
    db: Session,
) -> None:
    agent_run = db.get(AgentRun, run_id)
    if agent_run:
        agent_run.prompt_tokens = prompt_tokens
        agent_run.completion_tokens = completion_tokens
        agent_run.cost_usd = cost_usd
        db.commit()


def record_run_cost(run_id_str: str) -> None:
    """
    Fetches token counts from LangSmith and writes cost to agent_runs.
    Runs in a background thread — never raises, logs errors silently.
    """
    db = SessionLocal()
    try:
        from langsmith import Client as LangSmithClient
        client = LangSmithClient()
        run = client.read_run(run_id_str)

        prompt_tokens = run.prompt_tokens or 0
        completion_tokens = run.completion_tokens or 0
        cost_usd = (prompt_tokens * _INPUT_COST_PER_TOKEN) + (completion_tokens * _OUTPUT_COST_PER_TOKEN)

        _update_agent_run_cost(
            uuid.UUID(run_id_str),
            prompt_tokens,
            completion_tokens,
            cost_usd,
            db,
        )
        logger.info("agent_run %s cost=%.6f usd tokens=%d+%d", run_id_str, cost_usd, prompt_tokens, completion_tokens)
    except Exception as exc:
        logger.warning("LangSmith cost fetch failed for run %s: %s", run_id_str, exc)
    finally:
        db.close()

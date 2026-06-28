from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from common.database import get_db
from common.models import Allocation, CapitalCall, Fee

router = APIRouter()


@router.get("/counts")
def action_counts(db: Session = Depends(get_db)):
    """
    Platform-level counts of items requiring investor attention.

    Called automatically by the langgraph_sdk background poller (which defaults
    to http://localhost:8000/api/v1 when looking for the LangGraph Platform server).
    Also useful as a dashboard summary endpoint.

    Returns aggregate counts across all investors; no auth required for this demo.
    """
    overdue_fees = (
        db.query(func.count(Fee.fee_id))
        .filter(Fee.status == "Overdue")
        .scalar()
    ) or 0

    upcoming_fees = (
        db.query(func.count(Fee.fee_id))
        .filter(Fee.status == "Upcoming")
        .scalar()
    ) or 0

    upcoming_capital_calls = (
        db.query(func.count(CapitalCall.call_id))
        .filter(CapitalCall.status == "Upcoming")
        .scalar()
    ) or 0

    pending_allocations = (
        db.query(func.count(Allocation.allocation_id))
        .filter(Allocation.allocation_status == "Pending")
        .scalar()
    ) or 0

    total = overdue_fees + upcoming_fees + upcoming_capital_calls + pending_allocations

    return {
        "overdue_fees": overdue_fees,
        "upcoming_fees": upcoming_fees,
        "upcoming_capital_calls": upcoming_capital_calls,
        "pending_allocations": pending_allocations,
        "total": total,
    }

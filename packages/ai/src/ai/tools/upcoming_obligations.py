from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select

from common.models import Investor, CapitalCall, Fee, Allocation, Deal
from ai.tools._helpers import REPORT_DATE, get_fx_map, money


def get_upcoming_obligations(investor_id: str, db: Session) -> dict:
    try:
        investor = db.get(Investor, investor_id)
        if not investor:
            return {"error": f"Investor '{investor_id}' not found"}

        fx_map = get_fx_map(db)
        rc = investor.reporting_currency

        # Upcoming capital calls
        calls = (
            db.execute(
                select(CapitalCall)
                .where(
                    CapitalCall.investor_id == investor_id,
                    CapitalCall.status == "Upcoming",
                )
                .options(selectinload(CapitalCall.allocation).selectinload(Allocation.deal))
                .order_by(CapitalCall.due_date)
            )
            .scalars()
            .all()
        )

        capital_calls_out = []
        total_calls_rc = 0.0
        for c in calls:
            deal = c.allocation.deal
            amt = money(c.amount, c.currency, rc, fx_map)
            total_calls_rc += amt["reporting_amount"]
            capital_calls_out.append({
                "call_id": c.call_id,
                "deal_id": c.deal_id,
                "company_name": deal.company_name,
                "round": deal.round,
                "call_number": c.call_number,
                "call_date": str(c.call_date),
                "due_date": str(c.due_date),
                "overdue": c.due_date < REPORT_DATE,
                "amount": amt,
            })

        # Upcoming and overdue fees
        fees = (
            db.execute(
                select(Fee)
                .where(
                    Fee.investor_id == investor_id,
                    Fee.status.in_(["Upcoming", "Overdue"]),
                )
                .options(selectinload(Fee.allocation).selectinload(Allocation.deal))
                .order_by(Fee.due_date)
            )
            .scalars()
            .all()
        )

        fees_out = []
        total_fees_rc = 0.0
        for f in fees:
            deal = f.allocation.deal
            amt = money(f.amount, f.currency, rc, fx_map)
            total_fees_rc += amt["reporting_amount"]
            fees_out.append({
                "fee_id": f.fee_id,
                "deal_id": f.deal_id,
                "company_name": deal.company_name,
                "round": deal.round,
                "fee_type": f.fee_type,
                "period": f.period,
                "due_date": str(f.due_date),
                "status": f.status,
                "overdue": f.status == "Overdue",
                "amount": amt,
            })

        has_overdue = any(f["overdue"] for f in fees_out) or any(c["overdue"] for c in capital_calls_out)

        return {
            "investor_id": investor_id,
            "investor_name": investor.investor_name,
            "reporting_currency": rc,
            "report_date": str(REPORT_DATE),
            "has_overdue_items": has_overdue,
            "capital_calls": capital_calls_out,
            "fees": fees_out,
            "totals": {
                "capital_calls": {"amount": round(total_calls_rc, 2), "currency": rc},
                "fees": {"amount": round(total_fees_rc, 2), "currency": rc},
                "total": {"amount": round(total_calls_rc + total_fees_rc, 2), "currency": rc},
            },
        }
    except Exception as exc:
        return {"error": str(exc)}

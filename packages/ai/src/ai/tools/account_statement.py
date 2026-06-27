from decimal import Decimal
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import select

from common.models import Investor, StatementLine, Deal
from ai.tools._helpers import REPORT_DATE, get_fx_map, fx_convert, money


def get_account_statement(
    investor_id: str,
    db: Session,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    try:
        investor = db.get(Investor, investor_id)
        if not investor:
            return {"error": f"Investor '{investor_id}' not found"}

        fx_map = get_fx_map(db)
        rc = investor.reporting_currency

        stmt = (
            select(StatementLine)
            .where(StatementLine.investor_id == investor_id)
            .order_by(StatementLine.date)
        )

        parsed_start: date | None = None
        parsed_end: date | None = None

        if start_date:
            try:
                parsed_start = date.fromisoformat(start_date)
                stmt = stmt.where(StatementLine.date >= parsed_start)
            except ValueError:
                return {"error": f"Invalid start_date format '{start_date}'. Use YYYY-MM-DD."}

        if end_date:
            try:
                parsed_end = date.fromisoformat(end_date)
                stmt = stmt.where(StatementLine.date <= parsed_end)
            except ValueError:
                return {"error": f"Invalid end_date format '{end_date}'. Use YYYY-MM-DD."}

        lines = db.execute(stmt).scalars().all()

        # Get deal names for display
        deal_ids = list({ln.deal_id for ln in lines})
        deals = db.execute(select(Deal).where(Deal.deal_id.in_(deal_ids))).scalars().all()
        deal_map = {d.deal_id: d for d in deals}

        items = []
        net_rc = Decimal(0)
        total_in_rc = Decimal(0)   # positive (distributions, proceeds)
        total_out_rc = Decimal(0)  # negative in source, tracked as positive magnitude

        for ln in lines:
            deal = deal_map.get(ln.deal_id)
            amt_rc = fx_convert(ln.amount, ln.currency, rc, fx_map)
            net_rc += amt_rc
            if amt_rc >= 0:
                total_in_rc += amt_rc
            else:
                total_out_rc += abs(amt_rc)

            items.append({
                "line_id": ln.line_id,
                "date": str(ln.date),
                "type": ln.type,
                "deal_id": ln.deal_id,
                "company_name": deal.company_name if deal else ln.deal_id,
                "round": deal.round if deal else None,
                "amount": money(ln.amount, ln.currency, rc, fx_map),
                "reference_id": ln.reference_id,
            })

        return {
            "investor_id": investor_id,
            "investor_name": investor.investor_name,
            "reporting_currency": rc,
            "report_date": str(REPORT_DATE),
            "filters": {
                "start_date": str(parsed_start) if parsed_start else None,
                "end_date": str(parsed_end) if parsed_end else None,
            },
            "lines": items,
            "summary": {
                "total_out": {"amount": float(round(total_out_rc, 2)), "currency": rc},
                "total_in": {"amount": float(round(total_in_rc, 2)), "currency": rc},
                "net_cashflow": {"amount": float(round(net_rc, 2)), "currency": rc},
                "line_count": len(items),
            },
        }
    except Exception as exc:
        return {"error": str(exc)}

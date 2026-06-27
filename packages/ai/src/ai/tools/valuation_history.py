from sqlalchemy.orm import Session
from sqlalchemy import select

from common.models import Investor, Allocation, Deal, Valuation
from ai.tools._helpers import REPORT_DATE, get_fx_map, money, resolve_companies


def get_valuation_history(investor_id: str, db: Session, company_name: str) -> dict:
    try:
        investor = db.get(Investor, investor_id)
        if not investor:
            return {"error": f"Investor '{investor_id}' not found"}

        companies = resolve_companies(db, company_name)
        if not companies:
            return {"error": f"No company found matching '{company_name}'"}
        if len(companies) > 1:
            return {
                "disambiguation": True,
                "message": f"Found {len(companies)} companies matching '{company_name}'.",
                "matches": [
                    {"company_id": c.company_id, "company_name": c.company_name}
                    for c in companies
                ],
            }

        company = companies[0]
        fx_map = get_fx_map(db)
        rc = investor.reporting_currency

        # Get deals for this company that the investor is in
        investor_deal_ids = {
            row[0] for row in db.execute(
                select(Allocation.deal_id)
                .where(Allocation.investor_id == investor_id)
            ).all()
        }

        deals = (
            db.execute(
                select(Deal)
                .where(
                    Deal.company_id == company.company_id,
                    Deal.deal_id.in_(investor_deal_ids),
                )
                .order_by(Deal.deal_date)
            )
            .scalars()
            .all()
        )

        if not deals:
            return {
                "investor_id": investor_id,
                "company_name": company.company_name,
                "message": f"No position found in {company.company_name}",
                "rounds": [],
            }

        rounds_out = []
        for deal in deals:
            alloc = db.execute(
                select(Allocation).where(
                    Allocation.investor_id == investor_id,
                    Allocation.deal_id == deal.deal_id,
                )
            ).scalars().first()

            valuations = (
                db.execute(
                    select(Valuation)
                    .where(Valuation.deal_id == deal.deal_id)
                    .order_by(Valuation.valuation_date)
                )
                .scalars()
                .all()
            )

            entry_price = alloc.effective_share_price if alloc else deal.entry_share_price
            dc = deal.deal_currency

            marks = []
            for v in valuations:
                # Multiple vs investor's entry price (may differ from deal entry due to discount)
                multiple_vs_investor_entry = (
                    float(round(v.share_price / entry_price, 4))
                    if entry_price > 0 else None
                )
                marks.append({
                    "date": str(v.valuation_date),
                    "share_price": money(v.share_price, dc, rc, fx_map),
                    "company_valuation_m": float(v.company_valuation_m),
                    "multiple_vs_deal_entry": float(v.multiple_vs_entry),
                    "multiple_vs_investor_entry": multiple_vs_investor_entry,
                    "mark_source": v.mark_source,
                })

            rounds_out.append({
                "deal_id": deal.deal_id,
                "round": deal.round,
                "deal_date": str(deal.deal_date),
                "deal_currency": dc,
                "deal_status": deal.status,
                "entry_share_price": float(entry_price),
                "marks": marks,
            })

        return {
            "investor_id": investor_id,
            "company_id": company.company_id,
            "company_name": company.company_name,
            "sector": company.sector,
            "reporting_currency": rc,
            "report_date": str(REPORT_DATE),
            "rounds": rounds_out,
        }
    except Exception as exc:
        return {"error": str(exc)}

from decimal import Decimal
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select

from common.models import Investor, Allocation, Fee, Deal
from ai.tools._helpers import REPORT_DATE, get_fx_map, fx_convert, money, resolve_companies


def get_fee_detail(investor_id: str, db: Session, company_name: str | None = None) -> dict:
    try:
        investor = db.get(Investor, investor_id)
        if not investor:
            return {"error": f"Investor '{investor_id}' not found"}

        fx_map = get_fx_map(db)
        rc = investor.reporting_currency

        alloc_stmt = (
            select(Allocation)
            .where(Allocation.investor_id == investor_id)
            .options(selectinload(Allocation.deal), selectinload(Allocation.fees))
        )

        if company_name:
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
            deal_ids = [
                row[0] for row in db.execute(
                    select(Deal.deal_id).where(Deal.company_id == company.company_id)
                ).all()
            ]
            alloc_stmt = alloc_stmt.where(Allocation.deal_id.in_(deal_ids))

        allocations = db.execute(alloc_stmt).scalars().all()

        if not allocations:
            return {
                "investor_id": investor_id,
                "message": "No allocations found",
                "deals": [],
            }

        deals_out = []
        for alloc in allocations:
            deal = alloc.deal
            fees = alloc.fees

            def fee_sum(status_list: list[str]) -> Decimal:
                return sum(
                    fx_convert(f.amount, f.currency, rc, fx_map)
                    for f in fees
                    if f.status in status_list
                )

            paid_rc = fee_sum(["Paid"])
            upcoming_rc = fee_sum(["Upcoming"])
            overdue_rc = fee_sum(["Overdue"])

            fee_rows = []
            for f in sorted(fees, key=lambda x: x.due_date):
                fee_rows.append({
                    "fee_id": f.fee_id,
                    "fee_type": f.fee_type,
                    "period": f.period,
                    "fee_rate_pct": float(f.fee_rate_pct) if f.fee_rate_pct is not None else None,
                    "basis": f.basis,
                    "due_date": str(f.due_date),
                    "status": f.status,
                    "overdue": f.status == "Overdue",
                    "amount": money(f.amount, f.currency, rc, fx_map),
                })

            deals_out.append({
                "deal_id": alloc.deal_id,
                "company_name": deal.company_name,
                "round": deal.round,
                "deal_currency": alloc.deal_currency,
                "fee_discount": alloc.fee_discount,
                "standard_rates": {
                    "mgmt_fee_pct": float(deal.std_mgmt_fee_pct),
                    "performance_fee_pct": float(deal.std_performance_fee_pct),
                    "structuring_fee_pct": float(deal.std_structuring_fee_pct),
                    "admin_fee_usd": float(deal.std_admin_fee_usd),
                },
                "effective_rates": {
                    "mgmt_fee_pct": float(alloc.mgmt_fee_pct),
                    "performance_fee_pct": float(alloc.performance_fee_pct),
                    "structuring_fee_pct": float(alloc.structuring_fee_pct),
                    "admin_fee_usd": float(alloc.admin_fee_usd),
                },
                "fee_summary": {
                    "paid": {"amount": float(round(paid_rc, 2)), "currency": rc},
                    "upcoming": {"amount": float(round(upcoming_rc, 2)), "currency": rc},
                    "overdue": {"amount": float(round(overdue_rc, 2)), "currency": rc},
                },
                "fees": fee_rows,
            })

        return {
            "investor_id": investor_id,
            "investor_name": investor.investor_name,
            "reporting_currency": rc,
            "report_date": str(REPORT_DATE),
            "deals": deals_out,
        }
    except Exception as exc:
        return {"error": str(exc)}

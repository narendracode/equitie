from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import select

from common.models import Investor, Distribution, Deal, Allocation
from ai.tools._helpers import REPORT_DATE, get_fx_map, fx_convert, money, resolve_companies


def get_distributions(investor_id: str, db: Session, company_name: str | None = None) -> dict:
    try:
        investor = db.get(Investor, investor_id)
        if not investor:
            return {"error": f"Investor '{investor_id}' not found"}

        fx_map = get_fx_map(db)
        rc = investor.reporting_currency

        stmt = select(Distribution).where(Distribution.investor_id == investor_id)

        # Optionally filter by company
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
            deal_ids_for_company = [
                row[0] for row in db.execute(
                    select(Deal.deal_id).where(Deal.company_id == company.company_id)
                ).all()
            ]
            stmt = stmt.where(Distribution.deal_id.in_(deal_ids_for_company))

        distributions = (
            db.execute(stmt.order_by(Distribution.distribution_date))
            .scalars()
            .all()
        )

        if not distributions:
            label = f" in {company_name}" if company_name else ""
            return {
                "investor_id": investor_id,
                "investor_name": investor.investor_name,
                "message": f"No distributions received{label}",
                "distributions": [],
                "totals": {
                    "gross": {"amount": 0.0, "currency": rc},
                    "performance_fee": {"amount": 0.0, "currency": rc},
                    "net": {"amount": 0.0, "currency": rc},
                },
            }

        # Look up deal names
        deal_ids = list({d.deal_id for d in distributions})
        deals = db.execute(select(Deal).where(Deal.deal_id.in_(deal_ids))).scalars().all()
        deal_map = {d.deal_id: d for d in deals}

        items = []
        total_gross_rc = Decimal(0)
        total_fee_rc = Decimal(0)
        total_net_rc = Decimal(0)

        for dist in distributions:
            deal = deal_map.get(dist.deal_id)
            gross_rc = fx_convert(dist.gross_amount, dist.currency, rc, fx_map)
            fee_rc = fx_convert(dist.performance_fee_amount, dist.currency, rc, fx_map)
            net_rc = fx_convert(dist.net_amount, dist.currency, rc, fx_map)

            total_gross_rc += gross_rc
            total_fee_rc += fee_rc
            total_net_rc += net_rc

            items.append({
                "distribution_id": dist.distribution_id,
                "deal_id": dist.deal_id,
                "company_name": deal.company_name if deal else dist.deal_id,
                "round": deal.round if deal else None,
                "date": str(dist.distribution_date),
                "type": dist.distribution_type,
                "fraction_of_units": float(dist.fraction_of_units),
                "gross": money(dist.gross_amount, dist.currency, rc, fx_map),
                "performance_fee_pct": float(dist.performance_fee_pct),
                "performance_fee": money(dist.performance_fee_amount, dist.currency, rc, fx_map),
                "net": money(dist.net_amount, dist.currency, rc, fx_map),
            })

        return {
            "investor_id": investor_id,
            "investor_name": investor.investor_name,
            "reporting_currency": rc,
            "report_date": str(REPORT_DATE),
            "distributions": items,
            "totals": {
                "gross": {"amount": float(round(total_gross_rc, 2)), "currency": rc},
                "performance_fee": {"amount": float(round(total_fee_rc, 2)), "currency": rc},
                "net": {"amount": float(round(total_net_rc, 2)), "currency": rc},
            },
        }
    except Exception as exc:
        return {"error": str(exc)}

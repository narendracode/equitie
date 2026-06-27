from decimal import Decimal
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select

from common.models import Investor, Allocation, Deal
from ai.tools._helpers import (
    REPORT_DATE, get_fx_map, fx_convert, money,
    get_latest_valuations_for_deals, resolve_companies,
)


def get_position_detail(investor_id: str, db: Session, company_name: str) -> dict:
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
                "message": f"Found {len(companies)} companies matching '{company_name}'. Please specify which one.",
                "matches": [
                    {"company_id": c.company_id, "company_name": c.company_name, "sector": c.sector}
                    for c in companies
                ],
            }

        company = companies[0]
        fx_map = get_fx_map(db)
        rc = investor.reporting_currency

        # Get all deals for this company
        deals = (
            db.execute(select(Deal).where(Deal.company_id == company.company_id).order_by(Deal.deal_date))
            .scalars()
            .all()
        )

        deal_ids = [d.deal_id for d in deals]

        # Get investor's allocations for these deals
        allocations = (
            db.execute(
                select(Allocation)
                .where(
                    Allocation.investor_id == investor_id,
                    Allocation.deal_id.in_(deal_ids),
                )
                .options(
                    selectinload(Allocation.distributions),
                )
            )
            .scalars()
            .all()
        )

        if not allocations:
            return {
                "investor_id": investor_id,
                "company_id": company.company_id,
                "company_name": company.company_name,
                "sector": company.sector,
                "message": f"No position found in {company.company_name}",
                "rounds": [],
            }

        alloc_by_deal = {a.deal_id: a for a in allocations}
        latest_vals = get_latest_valuations_for_deals(db, [a.deal_id for a in allocations])

        rounds = []
        agg_committed_rc = Decimal(0)
        agg_contributed_rc = Decimal(0)
        agg_current_value_rc = Decimal(0)
        agg_net_dist_rc = Decimal(0)

        for deal in deals:
            alloc = alloc_by_deal.get(deal.deal_id)
            if not alloc:
                continue

            dc = alloc.deal_currency
            realised_fraction = min(
                sum(d.fraction_of_units for d in alloc.distributions),
                Decimal(1),
            )

            net_dist_deal = sum(
                fx_convert(d.net_amount, d.currency, dc, fx_map)
                for d in alloc.distributions
            )

            latest_val = latest_vals.get(alloc.deal_id)
            latest_price = latest_val.share_price if latest_val else alloc.effective_share_price

            if alloc.allocation_status == "Pending":
                current_value_deal = Decimal(0)
            elif deal.status in ("Exited", "Written Off"):
                current_value_deal = Decimal(0)
            else:
                remaining = Decimal(1) - realised_fraction
                current_value_deal = alloc.units * remaining * latest_price

            contributed = alloc.contributed_amount
            if contributed > 0:
                moic = float(round((current_value_deal + net_dist_deal) / contributed, 4))
                dpi = float(round(net_dist_deal / contributed, 4))
                rvpi = float(round(current_value_deal / contributed, 4))
            else:
                moic = dpi = rvpi = None

            committed_rc = fx_convert(alloc.commitment_amount, dc, rc, fx_map)
            contributed_rc = fx_convert(contributed, dc, rc, fx_map)
            current_value_rc = fx_convert(current_value_deal, dc, rc, fx_map)
            net_dist_rc = fx_convert(net_dist_deal, dc, rc, fx_map)

            agg_committed_rc += committed_rc
            agg_contributed_rc += contributed_rc
            agg_current_value_rc += current_value_rc
            agg_net_dist_rc += net_dist_rc

            # Build valuation history for this round
            val_history = []
            if latest_val:
                from common.models import Valuation
                from sqlalchemy import select as sa_select
                all_vals = (
                    db.execute(
                        sa_select(Valuation)
                        .where(Valuation.deal_id == deal.deal_id)
                        .order_by(Valuation.valuation_date)
                    )
                    .scalars()
                    .all()
                )
                for v in all_vals:
                    val_history.append({
                        "date": str(v.valuation_date),
                        "share_price": float(v.share_price),
                        "multiple_vs_entry": float(v.multiple_vs_entry),
                        "mark_source": v.mark_source,
                    })

            rounds.append({
                "deal_id": deal.deal_id,
                "round": deal.round,
                "instrument": deal.instrument,
                "deal_date": str(deal.deal_date),
                "deal_currency": dc,
                "deal_status": deal.status,
                "allocation_status": alloc.allocation_status,
                "committed": money(alloc.commitment_amount, dc, rc, fx_map),
                "contributed": money(contributed, dc, rc, fx_map),
                "outstanding_commitment": money(alloc.outstanding_commitment, dc, rc, fx_map),
                "units": float(alloc.units),
                "entry_share_price": float(alloc.effective_share_price),
                "latest_share_price": float(latest_price),
                "realised_fraction": float(realised_fraction),
                "current_value": money(current_value_deal, dc, rc, fx_map),
                "net_distributions": money(net_dist_deal, dc, rc, fx_map),
                "moic": moic,
                "dpi": dpi,
                "rvpi": rvpi,
                "valuation_history": val_history,
                "distributions": [
                    {
                        "date": str(d.distribution_date),
                        "type": d.distribution_type,
                        "gross": money(d.gross_amount, d.currency, rc, fx_map),
                        "performance_fee": money(d.performance_fee_amount, d.currency, rc, fx_map),
                        "net": money(d.net_amount, d.currency, rc, fx_map),
                        "fraction_of_units": float(d.fraction_of_units),
                    }
                    for d in alloc.distributions
                ],
            })

        # Aggregate across all rounds
        if agg_contributed_rc > 0:
            agg_moic = float(round((agg_current_value_rc + agg_net_dist_rc) / agg_contributed_rc, 4))
            agg_dpi = float(round(agg_net_dist_rc / agg_contributed_rc, 4))
            agg_rvpi = float(round(agg_current_value_rc / agg_contributed_rc, 4))
        else:
            agg_moic = agg_dpi = agg_rvpi = None

        return {
            "investor_id": investor_id,
            "company_id": company.company_id,
            "company_name": company.company_name,
            "sector": company.sector,
            "hq_country": company.hq_country,
            "company_status": company.status,
            "reporting_currency": rc,
            "report_date": str(REPORT_DATE),
            "aggregate": {
                "committed": {"amount": float(round(agg_committed_rc, 2)), "currency": rc},
                "contributed": {"amount": float(round(agg_contributed_rc, 2)), "currency": rc},
                "current_value": {"amount": float(round(agg_current_value_rc, 2)), "currency": rc},
                "net_distributions": {"amount": float(round(agg_net_dist_rc, 2)), "currency": rc},
                "moic": agg_moic,
                "dpi": agg_dpi,
                "rvpi": agg_rvpi,
            },
            "rounds": rounds,
        }
    except Exception as exc:
        return {"error": str(exc)}

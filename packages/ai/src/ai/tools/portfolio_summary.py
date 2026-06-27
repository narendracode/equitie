from decimal import Decimal
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select

from common.models import Investor, Allocation
from ai.tools._helpers import REPORT_DATE, get_fx_map, fx_convert, money, get_latest_valuations_for_deals


def get_portfolio_summary(investor_id: str, db: Session) -> dict:
    try:
        investor = db.get(Investor, investor_id)
        if not investor:
            return {"error": f"Investor '{investor_id}' not found"}

        fx_map = get_fx_map(db)
        rc = investor.reporting_currency

        allocations = (
            db.execute(
                select(Allocation)
                .where(Allocation.investor_id == investor_id)
                .options(
                    selectinload(Allocation.deal),
                    selectinload(Allocation.distributions),
                )
            )
            .scalars()
            .all()
        )

        if not allocations:
            return {
                "investor_id": investor_id,
                "investor_name": investor.investor_name,
                "reporting_currency": rc,
                "report_date": str(REPORT_DATE),
                "message": "No investments found",
                "positions": [],
                "totals": {
                    "committed": {"amount": 0.0, "currency": rc},
                    "contributed": {"amount": 0.0, "currency": rc},
                    "current_value": {"amount": 0.0, "currency": rc},
                    "net_distributions": {"amount": 0.0, "currency": rc},
                    "outstanding_commitment": {"amount": 0.0, "currency": rc},
                },
                "portfolio_moic": None,
                "portfolio_dpi": None,
                "portfolio_rvpi": None,
            }

        deal_ids = list({a.deal_id for a in allocations})
        latest_vals = get_latest_valuations_for_deals(db, deal_ids)

        positions = []
        total_committed_rc = Decimal(0)
        total_contributed_rc = Decimal(0)
        total_current_value_rc = Decimal(0)
        total_net_dist_rc = Decimal(0)
        total_outstanding_rc = Decimal(0)

        for alloc in allocations:
            deal = alloc.deal
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
                total = current_value_deal + net_dist_deal
                moic = float(round(total / contributed, 4))
                dpi = float(round(net_dist_deal / contributed, 4))
                rvpi = float(round(current_value_deal / contributed, 4))
            else:
                moic = dpi = rvpi = None

            committed_rc = fx_convert(alloc.commitment_amount, dc, rc, fx_map)
            contributed_rc = fx_convert(contributed, dc, rc, fx_map)
            current_value_rc = fx_convert(current_value_deal, dc, rc, fx_map)
            net_dist_rc_ = fx_convert(net_dist_deal, dc, rc, fx_map)
            outstanding_rc = fx_convert(alloc.outstanding_commitment, dc, rc, fx_map)

            total_committed_rc += committed_rc
            total_contributed_rc += contributed_rc
            total_current_value_rc += current_value_rc
            total_net_dist_rc += net_dist_rc_
            total_outstanding_rc += outstanding_rc

            positions.append({
                "deal_id": alloc.deal_id,
                "company_name": deal.company_name,
                "round": deal.round,
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
            })

        # Sort positions: active first, then exited, then written off
        status_order = {"Active": 0, "Exited": 1, "Written Off": 2}
        positions.sort(key=lambda p: (status_order.get(p["deal_status"], 9), p["company_name"]))

        if total_contributed_rc > 0:
            portfolio_moic = float(round((total_current_value_rc + total_net_dist_rc) / total_contributed_rc, 4))
            portfolio_dpi = float(round(total_net_dist_rc / total_contributed_rc, 4))
            portfolio_rvpi = float(round(total_current_value_rc / total_contributed_rc, 4))
        else:
            portfolio_moic = portfolio_dpi = portfolio_rvpi = None

        return {
            "investor_id": investor_id,
            "investor_name": investor.investor_name,
            "reporting_currency": rc,
            "report_date": str(REPORT_DATE),
            "portfolio_moic": portfolio_moic,
            "portfolio_dpi": portfolio_dpi,
            "portfolio_rvpi": portfolio_rvpi,
            "totals": {
                "committed": {"amount": float(round(total_committed_rc, 2)), "currency": rc},
                "contributed": {"amount": float(round(total_contributed_rc, 2)), "currency": rc},
                "current_value": {"amount": float(round(total_current_value_rc, 2)), "currency": rc},
                "net_distributions": {"amount": float(round(total_net_dist_rc, 2)), "currency": rc},
                "outstanding_commitment": {"amount": float(round(total_outstanding_rc, 2)), "currency": rc},
            },
            "positions": positions,
        }
    except Exception as exc:
        return {"error": str(exc)}

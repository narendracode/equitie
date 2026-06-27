from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from common.database import get_db
from common.models import Deal, Valuation, Allocation

router = APIRouter()


@router.get("")
def list_deals(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    deals = db.query(Deal).offset(skip).limit(limit).all()
    total = db.query(func.count(Deal.deal_id)).scalar()

    result = []
    for d in deals:
        latest_val = (
            db.query(Valuation)
            .filter(Valuation.deal_id == d.deal_id)
            .order_by(Valuation.valuation_date.desc())
            .first()
        )
        result.append({
            "deal_id": d.deal_id,
            "company_name": d.company_name,
            "round": d.round,
            "instrument": d.instrument,
            "deal_currency": d.deal_currency,
            "deal_date": d.deal_date,
            "equitie_allocation_m": float(d.equitie_allocation_m),
            "contributed_pct": float(d.contributed_pct),
            "status": d.status,
            "latest_share_price": float(latest_val.share_price) if latest_val else None,
            "latest_multiple": float(latest_val.multiple_vs_entry) if latest_val else None,
        })

    return {"total": total, "items": result}


@router.get("/{deal_id}")
def get_deal(deal_id: str, db: Session = Depends(get_db)):
    deal = db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    valuations = (
        db.query(Valuation)
        .filter(Valuation.deal_id == deal_id)
        .order_by(Valuation.valuation_date)
        .all()
    )

    investor_count = db.query(func.count(Allocation.allocation_id)).filter(
        Allocation.deal_id == deal_id
    ).scalar()

    return {
        "deal_id": deal.deal_id,
        "company_id": deal.company_id,
        "company_name": deal.company_name,
        "round": deal.round,
        "instrument": deal.instrument,
        "spv_name": deal.spv_name,
        "deal_currency": deal.deal_currency,
        "deal_date": deal.deal_date,
        "pre_money_valuation_m": float(deal.pre_money_valuation_m),
        "post_money_valuation_m": float(deal.post_money_valuation_m),
        "round_size_m": float(deal.round_size_m),
        "equitie_allocation_m": float(deal.equitie_allocation_m),
        "entry_share_price": float(deal.entry_share_price),
        "contributed_pct": float(deal.contributed_pct),
        "std_mgmt_fee_pct": float(deal.std_mgmt_fee_pct),
        "std_performance_fee_pct": float(deal.std_performance_fee_pct),
        "std_structuring_fee_pct": float(deal.std_structuring_fee_pct),
        "std_admin_fee_usd": float(deal.std_admin_fee_usd),
        "status": deal.status,
        "investor_count": investor_count,
        "valuations": [
            {
                "valuation_id": v.valuation_id,
                "valuation_date": v.valuation_date,
                "share_price": float(v.share_price),
                "company_valuation_m": float(v.company_valuation_m),
                "mark_source": v.mark_source,
                "multiple_vs_entry": float(v.multiple_vs_entry),
            }
            for v in valuations
        ],
    }

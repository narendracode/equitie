from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, select

from common.database import get_db
from common.models import Investor, Allocation, Deal, PortfolioCompany, StatementLine

router = APIRouter()


@router.get("")
def list_investors(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    investors = db.query(Investor).offset(skip).limit(limit).all()
    total = db.query(func.count(Investor.investor_id)).scalar()
    return {
        "total": total,
        "items": [
            {
                "investor_id": i.investor_id,
                "investor_name": i.investor_name,
                "investor_type": i.investor_type,
                "country": i.country,
                "reporting_currency": i.reporting_currency,
                "kyc_status": i.kyc_status,
                "tech_savviness": i.tech_savviness,
            }
            for i in investors
        ],
    }


@router.get("/{investor_id}")
def get_investor(investor_id: str, db: Session = Depends(get_db)):
    investor = db.get(Investor, investor_id)
    if not investor:
        raise HTTPException(status_code=404, detail="Investor not found")

    allocation_count = db.query(func.count(Allocation.allocation_id)).filter(
        Allocation.investor_id == investor_id
    ).scalar()

    sectors = (
        db.query(PortfolioCompany.sector, func.count(Allocation.allocation_id).label("n"))
        .join(Deal, Deal.company_id == PortfolioCompany.company_id)
        .join(Allocation, Allocation.deal_id == Deal.deal_id)
        .filter(Allocation.investor_id == investor_id)
        .group_by(PortfolioCompany.sector)
        .order_by(func.count(Allocation.allocation_id).desc())
        .all()
    )

    return {
        "investor_id": investor.investor_id,
        "investor_name": investor.investor_name,
        "investor_type": investor.investor_type,
        "country": investor.country,
        "reporting_currency": investor.reporting_currency,
        "age": investor.age,
        "tech_savviness": investor.tech_savviness,
        "kyc_status": investor.kyc_status,
        "onboarded_date": investor.onboarded_date,
        "email": investor.email,
        "deal_count": allocation_count,
        "top_sectors": [{"sector": s, "deals": n} for s, n in sectors],
    }


@router.get("/{investor_id}/allocations")
def get_investor_allocations(investor_id: str, db: Session = Depends(get_db)):
    investor = db.get(Investor, investor_id)
    if not investor:
        raise HTTPException(status_code=404, detail="Investor not found")

    allocations = (
        db.query(Allocation)
        .filter(Allocation.investor_id == investor_id)
        .all()
    )

    return {
        "investor_id": investor_id,
        "allocations": [
            {
                "allocation_id": a.allocation_id,
                "deal_id": a.deal_id,
                "deal_currency": a.deal_currency,
                "commitment_amount": float(a.commitment_amount),
                "contributed_amount": float(a.contributed_amount),
                "outstanding_commitment": float(a.outstanding_commitment),
                "units": float(a.units),
                "effective_share_price": float(a.effective_share_price),
                "mgmt_fee_pct": float(a.mgmt_fee_pct),
                "performance_fee_pct": float(a.performance_fee_pct),
                "structuring_fee_pct": float(a.structuring_fee_pct),
                "admin_fee_usd": float(a.admin_fee_usd),
                "fee_discount": a.fee_discount,
                "allocation_status": a.allocation_status,
                "allocation_date": a.allocation_date,
            }
            for a in allocations
        ],
    }


@router.get("/{investor_id}/statement")
def get_investor_statement(investor_id: str, db: Session = Depends(get_db)):
    investor = db.get(Investor, investor_id)
    if not investor:
        raise HTTPException(status_code=404, detail="Investor not found")

    lines = (
        db.query(StatementLine)
        .filter(StatementLine.investor_id == investor_id)
        .order_by(StatementLine.date)
        .all()
    )

    return {
        "investor_id": investor_id,
        "lines": [
            {
                "line_id": ln.line_id,
                "date": ln.date,
                "type": ln.type,
                "deal_id": ln.deal_id,
                "amount": float(ln.amount),
                "currency": ln.currency,
                "reference_id": ln.reference_id,
            }
            for ln in lines
        ],
    }

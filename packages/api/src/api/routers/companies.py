from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from common.database import get_db
from common.models import PortfolioCompany, Deal

router = APIRouter()


@router.get("")
def list_companies(db: Session = Depends(get_db)):
    companies = db.query(PortfolioCompany).all()
    return {
        "total": len(companies),
        "items": [
            {
                "company_id": c.company_id,
                "company_name": c.company_name,
                "sector": c.sector,
                "hq_country": c.hq_country,
                "status": c.status,
                "website": c.website,
            }
            for c in companies
        ],
    }


@router.get("/{company_id}")
def get_company(company_id: str, db: Session = Depends(get_db)):
    company = db.get(PortfolioCompany, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    deals = db.query(Deal).filter(Deal.company_id == company_id).order_by(Deal.deal_date).all()

    return {
        "company_id": company.company_id,
        "company_name": company.company_name,
        "sector": company.sector,
        "hq_country": company.hq_country,
        "status": company.status,
        "website": company.website,
        "deals": [
            {
                "deal_id": d.deal_id,
                "round": d.round,
                "instrument": d.instrument,
                "deal_currency": d.deal_currency,
                "deal_date": d.deal_date,
                "equitie_allocation_m": float(d.equitie_allocation_m),
                "contributed_pct": float(d.contributed_pct),
                "status": d.status,
            }
            for d in deals
        ],
    }

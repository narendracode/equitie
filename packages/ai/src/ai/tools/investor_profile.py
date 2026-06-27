from sqlalchemy.orm import Session
from sqlalchemy import select, func

from common.models import Investor, Allocation, Deal, PortfolioCompany
from ai.tools._helpers import REPORT_DATE


def get_investor_profile(investor_id: str, db: Session) -> dict:
    try:
        investor = db.get(Investor, investor_id)
        if not investor:
            return {"error": f"Investor '{investor_id}' not found"}

        deal_count = db.execute(
            select(func.count(Allocation.allocation_id))
            .where(Allocation.investor_id == investor_id)
        ).scalar() or 0

        sectors = db.execute(
            select(PortfolioCompany.sector, func.count(Allocation.allocation_id).label("n"))
            .join(Deal, Deal.company_id == PortfolioCompany.company_id)
            .join(Allocation, Allocation.deal_id == Deal.deal_id)
            .where(Allocation.investor_id == investor_id)
            .group_by(PortfolioCompany.sector)
            .order_by(func.count(Allocation.allocation_id).desc())
        ).all()

        return {
            "investor_id": investor.investor_id,
            "investor_name": investor.investor_name,
            "investor_type": investor.investor_type,
            "country": investor.country,
            "reporting_currency": investor.reporting_currency,
            "age": investor.age,
            "tech_savviness": investor.tech_savviness,
            "kyc_status": investor.kyc_status,
            "onboarded_date": str(investor.onboarded_date),
            "email": investor.email,
            "deal_count": deal_count,
            "top_sectors": [{"sector": s, "deal_count": n} for s, n in sectors],
            "report_date": str(REPORT_DATE),
        }
    except Exception as exc:
        return {"error": str(exc)}

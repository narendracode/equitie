from sqlalchemy.orm import Session
from sqlalchemy import select, func

from common.models import PortfolioCompany, Deal, Allocation
from ai.tools._helpers import resolve_companies


def search_company(db: Session, name_query: str) -> dict:
    try:
        if not name_query or len(name_query.strip()) < 2:
            return {"error": "Search query must be at least 2 characters"}

        companies = resolve_companies(db, name_query.strip())

        if not companies:
            return {
                "query": name_query,
                "matches": [],
                "message": f"No companies found matching '{name_query}'",
            }

        # Enrich with deal count
        deal_counts = dict(
            db.execute(
                select(Deal.company_id, func.count(Deal.deal_id).label("n"))
                .where(Deal.company_id.in_([c.company_id for c in companies]))
                .group_by(Deal.company_id)
            ).all()
        )

        return {
            "query": name_query,
            "matches": [
                {
                    "company_id": c.company_id,
                    "company_name": c.company_name,
                    "sector": c.sector,
                    "hq_country": c.hq_country,
                    "status": c.status,
                    "deal_count": deal_counts.get(c.company_id, 0),
                }
                for c in companies
            ],
        }
    except Exception as exc:
        return {"error": str(exc)}

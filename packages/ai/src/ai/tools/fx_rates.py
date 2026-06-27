from sqlalchemy.orm import Session
from sqlalchemy import select

from common.models import FxRate
from ai.tools._helpers import REPORT_DATE


def get_fx_rates(db: Session) -> dict:
    try:
        rates = db.execute(select(FxRate).order_by(FxRate.currency)).scalars().all()
        return {
            "report_date": str(REPORT_DATE),
            "base_currency": "USD",
            "rates": [
                {
                    "currency": r.currency,
                    "to_usd": float(r.to_usd),
                    "as_of": str(r.as_of),
                }
                for r in rates
            ],
        }
    except Exception as exc:
        return {"error": str(exc)}

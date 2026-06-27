from decimal import Decimal
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import select

from common.models import FxRate, PortfolioCompany, Valuation

# TODO: Replace with dynamic date once the platform moves beyond the case-study dataset.
# The seed data is synthetic and pinned to this report date throughout all tools.
REPORT_DATE = date(2026, 6, 25)


def get_fx_map(db: Session) -> dict[str, Decimal]:
    rows = db.execute(select(FxRate)).scalars().all()
    return {row.currency: row.to_usd for row in rows}


def fx_convert(amount: Decimal, from_currency: str, to_currency: str, fx_map: dict[str, Decimal]) -> Decimal:
    if from_currency == to_currency:
        return amount
    usd = amount * fx_map[from_currency]
    if to_currency == "USD":
        return usd
    return usd / fx_map[to_currency]


def money(amount: Decimal, deal_currency: str, reporting_currency: str, fx_map: dict[str, Decimal]) -> dict:
    """Return monetary amount in both deal currency and investor reporting currency."""
    reporting = fx_convert(amount, deal_currency, reporting_currency, fx_map)
    return {
        "amount": float(round(amount, 2)),
        "currency": deal_currency,
        "reporting_amount": float(round(reporting, 2)),
        "reporting_currency": reporting_currency,
    }


def get_latest_valuations_for_deals(db: Session, deal_ids: list[str]) -> dict[str, Valuation]:
    """Single query that returns the latest valuation per deal_id."""
    if not deal_ids:
        return {}
    rows = db.execute(
        select(Valuation)
        .where(Valuation.deal_id.in_(deal_ids))
        .order_by(Valuation.deal_id, Valuation.valuation_date.desc())
    ).scalars().all()
    latest: dict[str, Valuation] = {}
    for v in rows:
        if v.deal_id not in latest:
            latest[v.deal_id] = v
    return latest


def resolve_companies(db: Session, name_query: str) -> list[PortfolioCompany]:
    pattern = f"%{name_query}%"
    return (
        db.execute(
            select(PortfolioCompany)
            .where(PortfolioCompany.company_name.ilike(pattern))
            .order_by(PortfolioCompany.company_name)
        )
        .scalars()
        .all()
    )

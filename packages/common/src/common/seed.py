"""
Seed the database from CSV files in DATA_DIR.
Idempotent: uses ON CONFLICT DO NOTHING on each table's PK.
Run with: python -m common.seed
"""
import csv
import os
import sys
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from common.config import settings
from common.database import engine
from common.models import (
    PortfolioCompany,
    Deal,
    Valuation,
    Investor,
    Allocation,
    CapitalCall,
    Fee,
    Distribution,
    StatementLine,
    FxRate,
)


DATA_DIR = Path(settings.data_dir)


def _str(val: str) -> str | None:
    return val.strip() if val.strip() else None


def _date(val: str) -> date | None:
    v = val.strip()
    return date.fromisoformat(v) if v else None


def _dec(val: str) -> Decimal | None:
    v = val.strip()
    if not v:
        return None
    try:
        return Decimal(v)
    except InvalidOperation:
        return None


def _int(val: str) -> int | None:
    v = val.strip()
    return int(v) if v else None


def _bool_yn(val: str) -> bool:
    return val.strip().lower() == "yes"


def _read(filename: str) -> list[dict]:
    path = DATA_DIR / filename
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def seed_table(conn, model, rows: list[dict], pk: str) -> int:
    if not rows:
        return 0
    stmt = pg_insert(model.__table__).values(rows)
    stmt = stmt.on_conflict_do_nothing(index_elements=[pk])
    result = conn.execute(stmt)
    return result.rowcount


def run_seed() -> None:
    print(f"[seed] reading CSVs from {DATA_DIR}")

    portfolio_companies = [
        {
            "company_id": r["company_id"],
            "company_name": r["company_name"],
            "sector": r["sector"],
            "hq_country": r["hq_country"],
            "status": r["status"],
            "website": _str(r["website"]),
        }
        for r in _read("portfolio_companies.csv")
    ]

    fx_rates = [
        {
            "currency": r["currency"],
            "to_usd": _dec(r["to_usd"]),
            "as_of": _date(r["as_of"]),
        }
        for r in _read("fx_rates.csv")
    ]

    deals = [
        {
            "deal_id": r["deal_id"],
            "company_id": r["company_id"],
            "company_name": r["company_name"],
            "round": r["round"],
            "instrument": r["instrument"],
            "spv_name": r["spv_name"],
            "deal_currency": r["deal_currency"],
            "deal_date": _date(r["deal_date"]),
            "pre_money_valuation_m": _dec(r["pre_money_valuation_m"]),
            "post_money_valuation_m": _dec(r["post_money_valuation_m"]),
            "round_size_m": _dec(r["round_size_m"]),
            "equitie_allocation_m": _dec(r["equitie_allocation_m"]),
            "entry_share_price": _dec(r["entry_share_price"]),
            "contributed_pct": _dec(r["contributed_pct"]),
            "std_mgmt_fee_pct": _dec(r["std_mgmt_fee_pct"]),
            "std_performance_fee_pct": _dec(r["std_performance_fee_pct"]),
            "std_structuring_fee_pct": _dec(r["std_structuring_fee_pct"]),
            "std_admin_fee_usd": _dec(r["std_admin_fee_usd"]),
            "status": r["status"],
        }
        for r in _read("deals.csv")
    ]

    investors = [
        {
            "investor_id": r["investor_id"],
            "investor_name": r["investor_name"],
            "investor_type": r["investor_type"],
            "country": r["country"],
            "reporting_currency": r["reporting_currency"],
            "age": _int(r["age"]),
            "tech_savviness": r["tech_savviness"],
            "kyc_status": r["kyc_status"],
            "onboarded_date": _date(r["onboarded_date"]),
            "email": r["email"],
        }
        for r in _read("investors.csv")
    ]

    valuations = [
        {
            "valuation_id": r["valuation_id"],
            "deal_id": r["deal_id"],
            "valuation_date": _date(r["valuation_date"]),
            "share_price": _dec(r["share_price"]),
            "company_valuation_m": _dec(r["company_valuation_m"]),
            "mark_source": r["mark_source"],
            "multiple_vs_entry": _dec(r["multiple_vs_entry"]),
        }
        for r in _read("valuations.csv")
    ]

    allocations = [
        {
            "allocation_id": r["allocation_id"],
            "deal_id": r["deal_id"],
            "investor_id": r["investor_id"],
            "deal_currency": r["deal_currency"],
            "commitment_amount": _dec(r["commitment_amount"]),
            "price_discount_pct": _dec(r["price_discount_pct"]),
            "effective_share_price": _dec(r["effective_share_price"]),
            "units": _dec(r["units"]),
            "contributed_amount": _dec(r["contributed_amount"]),
            "outstanding_commitment": _dec(r["outstanding_commitment"]),
            "mgmt_fee_pct": _dec(r["mgmt_fee_pct"]),
            "performance_fee_pct": _dec(r["performance_fee_pct"]),
            "structuring_fee_pct": _dec(r["structuring_fee_pct"]),
            "admin_fee_usd": _dec(r["admin_fee_usd"]),
            "fee_discount": _bool_yn(r["fee_discount"]),
            "allocation_status": r["allocation_status"],
            "allocation_date": _date(r["allocation_date"]),
        }
        for r in _read("allocations.csv")
    ]

    capital_calls = [
        {
            "call_id": r["call_id"],
            "allocation_id": r["allocation_id"],
            "investor_id": r["investor_id"],
            "deal_id": r["deal_id"],
            "call_number": _int(r["call_number"]),
            "call_date": _date(r["call_date"]),
            "amount": _dec(r["amount"]),
            "currency": r["currency"],
            "due_date": _date(r["due_date"]),
            "status": r["status"],
        }
        for r in _read("capital_calls.csv")
    ]

    fees = [
        {
            "fee_id": r["fee_id"],
            "allocation_id": r["allocation_id"],
            "investor_id": r["investor_id"],
            "deal_id": r["deal_id"],
            "fee_type": r["fee_type"],
            "period": r["period"],
            "fee_rate_pct": _dec(r["fee_rate_pct"]),  # nullable for flat admin fees
            "basis": r["basis"],
            "amount": _dec(r["amount"]),
            "currency": r["currency"],
            "due_date": _date(r["due_date"]),
            "status": r["status"],
        }
        for r in _read("fees.csv")
    ]

    distributions = [
        {
            "distribution_id": r["distribution_id"],
            "deal_id": r["deal_id"],
            "allocation_id": r["allocation_id"],
            "investor_id": r["investor_id"],
            "distribution_date": _date(r["distribution_date"]),
            "distribution_type": r["distribution_type"],
            "gross_amount": _dec(r["gross_amount"]),
            "performance_fee_pct": _dec(r["performance_fee_pct"]),
            "performance_fee_amount": _dec(r["performance_fee_amount"]),
            "net_amount": _dec(r["net_amount"]),
            "currency": r["currency"],
            "fraction_of_units": _dec(r["fraction_of_units"]),
        }
        for r in _read("distributions.csv")
    ]

    statement_lines = [
        {
            "line_id": r["line_id"],
            "investor_id": r["investor_id"],
            "date": _date(r["date"]),
            "type": r["type"],
            "deal_id": r["deal_id"],
            "amount": _dec(r["amount"]),
            "currency": r["currency"],
            "reference_id": _str(r["reference_id"]),
        }
        for r in _read("statement_lines.csv")
    ]

    # insert in FK-respecting order
    with engine.begin() as conn:
        counts = {}
        counts["portfolio_companies"] = seed_table(conn, PortfolioCompany, portfolio_companies, "company_id")
        counts["fx_rates"]            = seed_table(conn, FxRate,            fx_rates,            "currency")
        counts["deals"]               = seed_table(conn, Deal,               deals,               "deal_id")
        counts["investors"]           = seed_table(conn, Investor,           investors,            "investor_id")
        counts["valuations"]          = seed_table(conn, Valuation,          valuations,           "valuation_id")
        counts["allocations"]         = seed_table(conn, Allocation,         allocations,          "allocation_id")
        counts["capital_calls"]       = seed_table(conn, CapitalCall,        capital_calls,        "call_id")
        counts["fees"]                = seed_table(conn, Fee,                fees,                 "fee_id")
        counts["distributions"]       = seed_table(conn, Distribution,       distributions,        "distribution_id")
        counts["statement_lines"]     = seed_table(conn, StatementLine,      statement_lines,      "line_id")

    for table, n in counts.items():
        status = "✓" if n > 0 else "— (already seeded)"
        print(f"  {table:<25} {n:>5} rows inserted {status}")

    print("[seed] done.")


if __name__ == "__main__":
    run_seed()

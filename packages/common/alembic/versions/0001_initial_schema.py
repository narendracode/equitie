"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-06-27

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "portfolio_companies",
        sa.Column("company_id", sa.String(20), primary_key=True),
        sa.Column("company_name", sa.String(200), nullable=False),
        sa.Column("sector", sa.String(100), nullable=False),
        sa.Column("hq_country", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("website", sa.String(200), nullable=True),
    )

    op.create_table(
        "fx_rates",
        sa.Column("currency", sa.String(5), primary_key=True),
        sa.Column("to_usd", sa.Numeric(10, 6), nullable=False),
        sa.Column("as_of", sa.Date, nullable=False),
    )

    op.create_table(
        "deals",
        sa.Column("deal_id", sa.String(20), primary_key=True),
        sa.Column("company_id", sa.String(20), sa.ForeignKey("portfolio_companies.company_id"), nullable=False),
        sa.Column("company_name", sa.String(200), nullable=False),
        sa.Column("round", sa.String(20), nullable=False),
        sa.Column("instrument", sa.String(20), nullable=False),
        sa.Column("spv_name", sa.String(300), nullable=False),
        sa.Column("deal_currency", sa.String(5), nullable=False),
        sa.Column("deal_date", sa.Date, nullable=False),
        sa.Column("pre_money_valuation_m", sa.Numeric(18, 4), nullable=False),
        sa.Column("post_money_valuation_m", sa.Numeric(18, 4), nullable=False),
        sa.Column("round_size_m", sa.Numeric(18, 4), nullable=False),
        sa.Column("equitie_allocation_m", sa.Numeric(18, 4), nullable=False),
        sa.Column("entry_share_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("contributed_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("std_mgmt_fee_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("std_performance_fee_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("std_structuring_fee_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("std_admin_fee_usd", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
    )

    op.create_table(
        "investors",
        sa.Column("investor_id", sa.String(20), primary_key=True),
        sa.Column("investor_name", sa.String(200), nullable=False),
        sa.Column("investor_type", sa.String(20), nullable=False),
        sa.Column("country", sa.String(100), nullable=False),
        sa.Column("reporting_currency", sa.String(5), nullable=False),
        sa.Column("age", sa.Integer, nullable=True),
        sa.Column("tech_savviness", sa.String(10), nullable=False),
        sa.Column("kyc_status", sa.String(20), nullable=False),
        sa.Column("onboarded_date", sa.Date, nullable=False),
        sa.Column("email", sa.String(200), nullable=False),
    )

    op.create_table(
        "valuations",
        sa.Column("valuation_id", sa.String(20), primary_key=True),
        sa.Column("deal_id", sa.String(20), sa.ForeignKey("deals.deal_id"), nullable=False),
        sa.Column("valuation_date", sa.Date, nullable=False),
        sa.Column("share_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("company_valuation_m", sa.Numeric(18, 4), nullable=False),
        sa.Column("mark_source", sa.String(30), nullable=False),
        sa.Column("multiple_vs_entry", sa.Numeric(10, 4), nullable=False),
    )

    op.create_table(
        "allocations",
        sa.Column("allocation_id", sa.String(20), primary_key=True),
        sa.Column("deal_id", sa.String(20), sa.ForeignKey("deals.deal_id"), nullable=False),
        sa.Column("investor_id", sa.String(20), sa.ForeignKey("investors.investor_id"), nullable=False),
        sa.Column("deal_currency", sa.String(5), nullable=False),
        sa.Column("commitment_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("price_discount_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("effective_share_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("units", sa.Numeric(20, 4), nullable=False),
        sa.Column("contributed_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("outstanding_commitment", sa.Numeric(18, 4), nullable=False),
        sa.Column("mgmt_fee_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("performance_fee_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("structuring_fee_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("admin_fee_usd", sa.Numeric(10, 2), nullable=False),
        sa.Column("fee_discount", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("allocation_status", sa.String(20), nullable=False),
        sa.Column("allocation_date", sa.Date, nullable=False),
    )

    op.create_table(
        "capital_calls",
        sa.Column("call_id", sa.String(20), primary_key=True),
        sa.Column("allocation_id", sa.String(20), sa.ForeignKey("allocations.allocation_id"), nullable=False),
        sa.Column("investor_id", sa.String(20), sa.ForeignKey("investors.investor_id"), nullable=False),
        sa.Column("deal_id", sa.String(20), sa.ForeignKey("deals.deal_id"), nullable=False),
        sa.Column("call_number", sa.Integer, nullable=False),
        sa.Column("call_date", sa.Date, nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency", sa.String(5), nullable=False),
        sa.Column("due_date", sa.Date, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
    )

    op.create_table(
        "fees",
        sa.Column("fee_id", sa.String(20), primary_key=True),
        sa.Column("allocation_id", sa.String(20), sa.ForeignKey("allocations.allocation_id"), nullable=False),
        sa.Column("investor_id", sa.String(20), sa.ForeignKey("investors.investor_id"), nullable=False),
        sa.Column("deal_id", sa.String(20), sa.ForeignKey("deals.deal_id"), nullable=False),
        sa.Column("fee_type", sa.String(30), nullable=False),
        sa.Column("period", sa.String(10), nullable=False),
        sa.Column("fee_rate_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("basis", sa.String(20), nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency", sa.String(5), nullable=False),
        sa.Column("due_date", sa.Date, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
    )

    op.create_table(
        "distributions",
        sa.Column("distribution_id", sa.String(20), primary_key=True),
        sa.Column("deal_id", sa.String(20), sa.ForeignKey("deals.deal_id"), nullable=False),
        sa.Column("allocation_id", sa.String(20), sa.ForeignKey("allocations.allocation_id"), nullable=False),
        sa.Column("investor_id", sa.String(20), sa.ForeignKey("investors.investor_id"), nullable=False),
        sa.Column("distribution_date", sa.Date, nullable=False),
        sa.Column("distribution_type", sa.String(30), nullable=False),
        sa.Column("gross_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("performance_fee_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("performance_fee_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("net_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency", sa.String(5), nullable=False),
        sa.Column("fraction_of_units", sa.Numeric(6, 4), nullable=False),
    )

    op.create_table(
        "statement_lines",
        sa.Column("line_id", sa.String(20), primary_key=True),
        sa.Column("investor_id", sa.String(20), sa.ForeignKey("investors.investor_id"), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("type", sa.String(40), nullable=False),
        sa.Column("deal_id", sa.String(20), sa.ForeignKey("deals.deal_id"), nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency", sa.String(5), nullable=False),
        sa.Column("reference_id", sa.String(20), nullable=True),
    )

    # useful indexes
    op.create_index("ix_allocations_investor_id", "allocations", ["investor_id"])
    op.create_index("ix_allocations_deal_id", "allocations", ["deal_id"])
    op.create_index("ix_capital_calls_allocation_id", "capital_calls", ["allocation_id"])
    op.create_index("ix_fees_allocation_id", "fees", ["allocation_id"])
    op.create_index("ix_fees_investor_id", "fees", ["investor_id"])
    op.create_index("ix_distributions_allocation_id", "distributions", ["allocation_id"])
    op.create_index("ix_statement_lines_investor_id", "statement_lines", ["investor_id"])
    op.create_index("ix_valuations_deal_id", "valuations", ["deal_id"])
    op.create_index("ix_deals_company_id", "deals", ["company_id"])


def downgrade() -> None:
    op.drop_table("statement_lines")
    op.drop_table("distributions")
    op.drop_table("fees")
    op.drop_table("capital_calls")
    op.drop_table("allocations")
    op.drop_table("valuations")
    op.drop_table("investors")
    op.drop_table("deals")
    op.drop_table("fx_rates")
    op.drop_table("portfolio_companies")

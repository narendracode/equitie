from decimal import Decimal
from datetime import date
from sqlalchemy import String, Numeric, Date, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from common.database import Base


class Deal(Base):
    __tablename__ = "deals"

    deal_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(20), ForeignKey("portfolio_companies.company_id"))
    company_name: Mapped[str] = mapped_column(String(200))
    round: Mapped[str] = mapped_column(String(20))
    instrument: Mapped[str] = mapped_column(String(20))
    spv_name: Mapped[str] = mapped_column(String(300))
    deal_currency: Mapped[str] = mapped_column(String(5))
    deal_date: Mapped[date] = mapped_column(Date)
    pre_money_valuation_m: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    post_money_valuation_m: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    round_size_m: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    equitie_allocation_m: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    entry_share_price: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    contributed_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    std_mgmt_fee_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    std_performance_fee_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    std_structuring_fee_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    std_admin_fee_usd: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    status: Mapped[str] = mapped_column(String(20))

    company: Mapped["PortfolioCompany"] = relationship("PortfolioCompany", back_populates="deals")
    valuations: Mapped[list["Valuation"]] = relationship("Valuation", back_populates="deal")
    allocations: Mapped[list["Allocation"]] = relationship("Allocation", back_populates="deal")

    def __repr__(self) -> str:
        return f"<Deal {self.deal_id} {self.company_name} {self.round}>"

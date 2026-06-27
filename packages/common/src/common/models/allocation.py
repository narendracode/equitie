from decimal import Decimal
from datetime import date
from sqlalchemy import String, Numeric, Date, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from common.database import Base


class Allocation(Base):
    __tablename__ = "allocations"

    allocation_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    deal_id: Mapped[str] = mapped_column(String(20), ForeignKey("deals.deal_id"))
    investor_id: Mapped[str] = mapped_column(String(20), ForeignKey("investors.investor_id"))
    deal_currency: Mapped[str] = mapped_column(String(5))
    commitment_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    price_discount_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    effective_share_price: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    units: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    contributed_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    outstanding_commitment: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    mgmt_fee_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    performance_fee_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    structuring_fee_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    admin_fee_usd: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    fee_discount: Mapped[bool] = mapped_column(Boolean, default=False)
    allocation_status: Mapped[str] = mapped_column(String(20))
    allocation_date: Mapped[date] = mapped_column(Date)

    deal: Mapped["Deal"] = relationship("Deal", back_populates="allocations")
    investor: Mapped["Investor"] = relationship("Investor", back_populates="allocations")
    capital_calls: Mapped[list["CapitalCall"]] = relationship("CapitalCall", back_populates="allocation")
    fees: Mapped[list["Fee"]] = relationship("Fee", back_populates="allocation")
    distributions: Mapped[list["Distribution"]] = relationship("Distribution", back_populates="allocation")

    def __repr__(self) -> str:
        return f"<Allocation {self.allocation_id} inv={self.investor_id} deal={self.deal_id}>"

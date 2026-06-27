from decimal import Decimal
from datetime import date
from sqlalchemy import String, Numeric, Date, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from common.database import Base


class Distribution(Base):
    __tablename__ = "distributions"

    distribution_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    deal_id: Mapped[str] = mapped_column(String(20), ForeignKey("deals.deal_id"))
    allocation_id: Mapped[str] = mapped_column(String(20), ForeignKey("allocations.allocation_id"))
    investor_id: Mapped[str] = mapped_column(String(20), ForeignKey("investors.investor_id"))
    distribution_date: Mapped[date] = mapped_column(Date)
    distribution_type: Mapped[str] = mapped_column(String(30))
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    performance_fee_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    performance_fee_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    net_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    currency: Mapped[str] = mapped_column(String(5))
    fraction_of_units: Mapped[Decimal] = mapped_column(Numeric(6, 4))

    allocation: Mapped["Allocation"] = relationship("Allocation", back_populates="distributions")

    def __repr__(self) -> str:
        return f"<Distribution {self.distribution_id} {self.distribution_type} alloc={self.allocation_id}>"

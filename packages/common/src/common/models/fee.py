from decimal import Decimal
from datetime import date
from sqlalchemy import String, Numeric, Date, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from common.database import Base


class Fee(Base):
    __tablename__ = "fees"

    fee_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    allocation_id: Mapped[str] = mapped_column(String(20), ForeignKey("allocations.allocation_id"))
    investor_id: Mapped[str] = mapped_column(String(20), ForeignKey("investors.investor_id"))
    deal_id: Mapped[str] = mapped_column(String(20), ForeignKey("deals.deal_id"))
    fee_type: Mapped[str] = mapped_column(String(30))
    period: Mapped[str] = mapped_column(String(10))
    fee_rate_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    basis: Mapped[str] = mapped_column(String(20))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    currency: Mapped[str] = mapped_column(String(5))
    due_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20))

    allocation: Mapped["Allocation"] = relationship("Allocation", back_populates="fees")

    def __repr__(self) -> str:
        return f"<Fee {self.fee_id} {self.fee_type} alloc={self.allocation_id}>"

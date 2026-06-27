from decimal import Decimal
from datetime import date
from sqlalchemy import String, Numeric, Date, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from common.database import Base


class CapitalCall(Base):
    __tablename__ = "capital_calls"

    call_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    allocation_id: Mapped[str] = mapped_column(String(20), ForeignKey("allocations.allocation_id"))
    investor_id: Mapped[str] = mapped_column(String(20), ForeignKey("investors.investor_id"))
    deal_id: Mapped[str] = mapped_column(String(20), ForeignKey("deals.deal_id"))
    call_number: Mapped[int] = mapped_column(Integer)
    call_date: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    currency: Mapped[str] = mapped_column(String(5))
    due_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20))

    allocation: Mapped["Allocation"] = relationship("Allocation", back_populates="capital_calls")

    def __repr__(self) -> str:
        return f"<CapitalCall {self.call_id} alloc={self.allocation_id} status={self.status}>"

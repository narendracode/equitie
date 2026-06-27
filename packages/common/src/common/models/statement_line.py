from decimal import Decimal
from datetime import date
from sqlalchemy import String, Numeric, Date, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from common.database import Base


class StatementLine(Base):
    __tablename__ = "statement_lines"

    line_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    investor_id: Mapped[str] = mapped_column(String(20), ForeignKey("investors.investor_id"))
    date: Mapped[date] = mapped_column(Date)
    type: Mapped[str] = mapped_column(String(40))
    deal_id: Mapped[str] = mapped_column(String(20), ForeignKey("deals.deal_id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    currency: Mapped[str] = mapped_column(String(5))
    reference_id: Mapped[str | None] = mapped_column(String(20), nullable=True)

    investor: Mapped["Investor"] = relationship("Investor", back_populates="statement_lines")

    def __repr__(self) -> str:
        return f"<StatementLine {self.line_id} inv={self.investor_id} {self.type}>"

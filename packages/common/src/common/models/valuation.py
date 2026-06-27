from decimal import Decimal
from datetime import date
from sqlalchemy import String, Numeric, Date, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from common.database import Base


class Valuation(Base):
    __tablename__ = "valuations"

    valuation_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    deal_id: Mapped[str] = mapped_column(String(20), ForeignKey("deals.deal_id"))
    valuation_date: Mapped[date] = mapped_column(Date)
    share_price: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    company_valuation_m: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    mark_source: Mapped[str] = mapped_column(String(30))
    multiple_vs_entry: Mapped[Decimal] = mapped_column(Numeric(10, 4))

    deal: Mapped["Deal"] = relationship("Deal", back_populates="valuations")

    def __repr__(self) -> str:
        return f"<Valuation {self.valuation_id} deal={self.deal_id} {self.valuation_date}>"

from decimal import Decimal
from datetime import date
from sqlalchemy import String, Numeric, Date
from sqlalchemy.orm import Mapped, mapped_column
from common.database import Base


class FxRate(Base):
    __tablename__ = "fx_rates"

    currency: Mapped[str] = mapped_column(String(5), primary_key=True)
    to_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6))
    as_of: Mapped[date] = mapped_column(Date)

    def __repr__(self) -> str:
        return f"<FxRate {self.currency} → {self.to_usd} USD>"

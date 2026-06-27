from datetime import date
from sqlalchemy import String, Integer, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship
from common.database import Base


class Investor(Base):
    __tablename__ = "investors"

    investor_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    investor_name: Mapped[str] = mapped_column(String(200))
    investor_type: Mapped[str] = mapped_column(String(20))
    country: Mapped[str] = mapped_column(String(100))
    reporting_currency: Mapped[str] = mapped_column(String(5))
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tech_savviness: Mapped[str] = mapped_column(String(10))
    kyc_status: Mapped[str] = mapped_column(String(20))
    onboarded_date: Mapped[date] = mapped_column(Date)
    email: Mapped[str] = mapped_column(String(200))

    allocations: Mapped[list["Allocation"]] = relationship("Allocation", back_populates="investor")
    statement_lines: Mapped[list["StatementLine"]] = relationship("StatementLine", back_populates="investor")

    def __repr__(self) -> str:
        return f"<Investor {self.investor_id} {self.investor_name}>"

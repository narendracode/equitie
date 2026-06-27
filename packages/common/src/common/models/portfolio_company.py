from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from common.database import Base


class PortfolioCompany(Base):
    __tablename__ = "portfolio_companies"

    company_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    company_name: Mapped[str] = mapped_column(String(200))
    sector: Mapped[str] = mapped_column(String(100))
    hq_country: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20))
    website: Mapped[str | None] = mapped_column(String(200), nullable=True)

    deals: Mapped[list["Deal"]] = relationship("Deal", back_populates="company")

    def __repr__(self) -> str:
        return f"<PortfolioCompany {self.company_id} {self.company_name}>"

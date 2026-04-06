from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class PriceIndex(Base):
    __tablename__ = "price_indices"

    id: Mapped[int] = mapped_column(primary_key=True)
    country_id: Mapped[int] = mapped_column(ForeignKey("countries.id"), index=True)
    region_id: Mapped[int | None] = mapped_column(ForeignKey("regions.id"))
    quarter: Mapped[str] = mapped_column(String(7))  # e.g. "2024Q1"
    year: Mapped[int] = mapped_column(Integer)
    index_value: Mapped[float] = mapped_column(Float)
    base_year: Mapped[int] = mapped_column(Integer, default=2015)
    source: Mapped[str] = mapped_column(String(50))  # EUROSTAT, NSO, NSI, CYSTAT, DZS

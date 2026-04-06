from geoalchemy2 import Geometry
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base


class Country(Base):
    __tablename__ = "countries"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(2), unique=True, index=True)  # MT, BG, CY, HR
    name: Mapped[str] = mapped_column(String(100))
    currency: Mapped[str] = mapped_column(String(3), default="EUR")

    regions: Mapped[list["Region"]] = relationship(back_populates="country")


class Region(Base):
    __tablename__ = "regions"

    id: Mapped[int] = mapped_column(primary_key=True)
    country_id: Mapped[int] = mapped_column(ForeignKey("countries.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    nuts_code: Mapped[str | None] = mapped_column(String(10), index=True)
    geometry = mapped_column(Geometry("MULTIPOLYGON", srid=4326), nullable=True)

    country: Mapped["Country"] = relationship(back_populates="regions")

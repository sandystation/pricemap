import enum
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class PropertyType(str, enum.Enum):
    APARTMENT = "apartment"
    HOUSE = "house"
    VILLA = "villa"
    STUDIO = "studio"
    MAISONETTE = "maisonette"
    PENTHOUSE = "penthouse"
    COMMERCIAL = "commercial"
    LAND = "land"


class PropertyCondition(str, enum.Enum):
    NEW = "new"
    EXCELLENT = "excellent"
    GOOD = "good"
    NEEDS_RENOVATION = "needs_renovation"
    SHELL = "shell"


class PriceType(str, enum.Enum):
    ASKING = "asking"
    TRANSACTION = "transaction"
    ASSESSED = "assessed"


class DataSource(str, enum.Enum):
    # Malta
    MT_PPR = "mt_ppr"
    MT_PROPERTYMARKET = "mt_propertymarket"
    # Bulgaria
    BG_IMOT = "bg_imot"
    BG_HOMES = "bg_homes"
    # Cyprus (Phase 2)
    CY_BAZARAKI = "cy_bazaraki"
    CY_BUYSELL = "cy_buysell"
    # Croatia (Phase 2)
    HR_NEKRETNINE = "hr_nekretnine"
    HR_NJUSKALO = "hr_njuskalo"


class Property(Base):
    __tablename__ = "properties"

    id: Mapped[int] = mapped_column(primary_key=True)
    country_id: Mapped[int] = mapped_column(ForeignKey("countries.id"), index=True)
    region_id: Mapped[int | None] = mapped_column(ForeignKey("regions.id"), index=True)
    external_id: Mapped[str | None] = mapped_column(String(200))
    source: Mapped[DataSource] = mapped_column(Enum(DataSource))

    # Address
    address_raw: Mapped[str | None] = mapped_column(Text)
    address_normalized: Mapped[str | None] = mapped_column(Text)
    locality: Mapped[str | None] = mapped_column(String(200), index=True)
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)
    geometry = mapped_column(Geometry("POINT", srid=4326), nullable=True)

    # Property characteristics
    property_type: Mapped[PropertyType] = mapped_column(Enum(PropertyType))
    area_sqm: Mapped[float | None] = mapped_column(Float)
    floor: Mapped[int | None] = mapped_column(Integer)
    total_floors: Mapped[int | None] = mapped_column(Integer)
    rooms: Mapped[int | None] = mapped_column(Integer)
    bedrooms: Mapped[int | None] = mapped_column(Integer)
    bathrooms: Mapped[int | None] = mapped_column(Integer)
    year_built: Mapped[int | None] = mapped_column(Integer)
    year_renovated: Mapped[int | None] = mapped_column(Integer)
    condition: Mapped[PropertyCondition | None] = mapped_column(Enum(PropertyCondition))

    # Amenities
    has_parking: Mapped[bool | None] = mapped_column(default=None)
    has_garden: Mapped[bool | None] = mapped_column(default=None)
    has_pool: Mapped[bool | None] = mapped_column(default=None)
    has_elevator: Mapped[bool | None] = mapped_column(default=None)
    has_balcony: Mapped[bool | None] = mapped_column(default=None)
    energy_class: Mapped[str | None] = mapped_column(String(5))

    # Computed spatial features
    distance_coast_m: Mapped[float | None] = mapped_column(Float)
    distance_center_m: Mapped[float | None] = mapped_column(Float)

    # Pricing
    price_eur: Mapped[float | None] = mapped_column(Float)
    price_original: Mapped[float | None] = mapped_column(Float)
    price_currency: Mapped[str] = mapped_column(String(3), default="EUR")
    price_type: Mapped[PriceType] = mapped_column(Enum(PriceType))
    price_adjusted_eur: Mapped[float | None] = mapped_column(Float)

    # Dates
    listing_date: Mapped[datetime | None] = mapped_column(DateTime)
    transaction_date: Mapped[datetime | None] = mapped_column(DateTime)
    scraped_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Status
    is_active: Mapped[bool] = mapped_column(default=True)
    dedup_hash: Mapped[str | None] = mapped_column(String(64), index=True)

    __table_args__ = (
        Index("ix_properties_geo", "geometry", postgresql_using="gist"),
        Index("ix_properties_country_type_price", "country_id", "property_type", "price_adjusted_eur"),
    )

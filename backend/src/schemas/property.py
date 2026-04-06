from pydantic import BaseModel, Field


class PropertySearchParams(BaseModel):
    """Query parameters for spatial property search."""

    country_code: str = Field(..., min_length=2, max_length=2)
    min_lat: float = Field(..., ge=-90, le=90)
    max_lat: float = Field(..., ge=-90, le=90)
    min_lon: float = Field(..., ge=-180, le=180)
    max_lon: float = Field(..., ge=-180, le=180)
    property_type: str | None = None
    min_price: float | None = None
    max_price: float | None = None
    limit: int = Field(default=100, ge=1, le=500)


class PropertyResponse(BaseModel):
    """Property detail response."""

    id: int
    country_code: str
    address: str | None
    locality: str | None
    lat: float | None
    lon: float | None
    property_type: str
    area_sqm: float | None
    floor: int | None
    rooms: int | None
    bedrooms: int | None
    year_built: int | None
    condition: str | None
    price_eur: float | None
    price_per_sqm: float | None
    price_type: str
    source: str
    listing_date: str | None
    is_active: bool


class PropertyListResponse(BaseModel):
    """Paginated property list."""

    items: list[PropertyResponse]
    total: int

from pydantic import BaseModel, Field

from src.models.property import PropertyCondition, PropertyType


class ValuationRequest(BaseModel):
    """Input for property valuation estimate."""

    country_code: str = Field(..., min_length=2, max_length=2, examples=["MT"])
    address: str | None = Field(None, examples=["123 Republic Street, Valletta"])
    lat: float | None = Field(None, ge=-90, le=90)
    lon: float | None = Field(None, ge=-180, le=180)

    property_type: PropertyType
    area_sqm: float = Field(..., gt=0, le=10000)
    floor: int | None = Field(None, ge=-2, le=100)
    total_floors: int | None = Field(None, ge=1, le=100)
    rooms: int | None = Field(None, ge=1, le=50)
    bedrooms: int | None = Field(None, ge=0, le=20)
    bathrooms: int | None = Field(None, ge=0, le=20)
    year_built: int | None = Field(None, ge=1400, le=2030)
    year_renovated: int | None = Field(None, ge=1900, le=2030)
    condition: PropertyCondition | None = None

    has_parking: bool | None = None
    has_garden: bool | None = None
    has_pool: bool | None = None
    has_elevator: bool | None = None
    has_balcony: bool | None = None


class ComparableProperty(BaseModel):
    """A comparable property used in the valuation."""

    id: int
    address: str | None
    lat: float
    lon: float
    property_type: str
    area_sqm: float
    price_eur: float
    price_per_sqm: float
    distance_m: float
    listing_date: str | None
    source: str


class ValuationResponse(BaseModel):
    """Valuation result."""

    estimate_eur: float
    confidence_low: float
    confidence_high: float
    confidence_score: float = Field(ge=0, le=100)
    confidence_label: str  # "High", "Moderate", "Low"
    price_per_sqm: float
    comparables: list[ComparableProperty]
    feature_importance: dict[str, float]
    model_version: str
    data_freshness: str | None
    method: str  # "model" or "comparables"

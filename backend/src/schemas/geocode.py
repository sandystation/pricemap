from pydantic import BaseModel, Field


class GeocodeRequest(BaseModel):
    address: str
    country_code: str = Field(..., min_length=2, max_length=2)


class GeocodeResponse(BaseModel):
    lat: float
    lon: float
    display_name: str
    locality: str | None = None
    confidence: float = Field(ge=0, le=1)

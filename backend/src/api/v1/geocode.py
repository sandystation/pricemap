from fastapi import APIRouter, Query

from src.schemas.geocode import GeocodeResponse
from src.services.geocoding_service import GeocodingService

router = APIRouter()


@router.get("", response_model=GeocodeResponse)
async def geocode_address(
    address: str = Query(..., min_length=3),
    country_code: str = Query(..., min_length=2, max_length=2),
):
    """Geocode an address to lat/lon coordinates. Results are cached."""
    service = GeocodingService()
    return await service.geocode(address=address, country_code=country_code)

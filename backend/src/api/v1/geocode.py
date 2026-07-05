from fastapi import APIRouter, Depends, Query

from src.core.auth import require_user
from src.schemas.geocode import GeocodeResponse, GeocodeSearchResponse
from src.services.geocode_rate_limit import enforce_search_rate_limit
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


@router.get("/search", response_model=GeocodeSearchResponse)
async def geocode_search(
    q: str = Query(..., min_length=3, max_length=120),
    country_code: str = Query("MT", min_length=2, max_length=2),
    limit: int = Query(6, ge=1, le=10),
    user_id: str = Depends(require_user),
):
    """Malta address typeahead suggestions (auth-gated + per-user rate-limited).

    Degrades to an empty list on any upstream error so the form falls back to a
    free-typed address.
    """
    await enforce_search_rate_limit(f"user:{user_id}")
    service = GeocodingService()
    try:
        results = await service.search(q=q, country_code=country_code, limit=limit)
    except Exception:
        results = []
    return GeocodeSearchResponse(results=results)

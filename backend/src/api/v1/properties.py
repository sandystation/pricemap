from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.schemas.property import PropertyListResponse, PropertyResponse
from src.services.property_service import PropertyService

router = APIRouter()


@router.get("/search", response_model=PropertyListResponse)
async def search_properties(
    country_code: str = Query(..., min_length=2, max_length=2),
    min_lat: float = Query(...),
    max_lat: float = Query(...),
    min_lon: float = Query(...),
    max_lon: float = Query(...),
    property_type: str | None = Query(None),
    min_price: float | None = Query(None),
    max_price: float | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Search properties within a bounding box."""
    service = PropertyService(db)
    return await service.search(
        country_code=country_code,
        min_lat=min_lat,
        max_lat=max_lat,
        min_lon=min_lon,
        max_lon=max_lon,
        property_type=property_type,
        min_price=min_price,
        max_price=max_price,
        limit=limit,
    )


@router.get("/{property_id}", response_model=PropertyResponse)
async def get_property(
    property_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get property details by ID."""
    service = PropertyService(db)
    return await service.get_by_id(property_id)

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.services.stats_service import StatsService

router = APIRouter()


@router.get("/{country_code}")
async def get_country_stats(
    country_code: str,
    region: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get aggregate market statistics for a country/region."""
    service = StatsService(db)
    return await service.get_stats(country_code=country_code, region=region)


@router.get("/{country_code}/heatmap")
async def get_heatmap(
    country_code: str,
    db: AsyncSession = Depends(get_db),
):
    """Get GeoJSON price heatmap data for a country."""
    service = StatsService(db)
    return await service.get_heatmap(country_code=country_code)

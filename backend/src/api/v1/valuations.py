from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.schemas.valuation import ValuationRequest, ValuationResponse
from src.services.valuation_service import ValuationService

router = APIRouter()


@router.post("/estimate", response_model=ValuationResponse)
async def estimate_value(
    request: ValuationRequest,
    db: AsyncSession = Depends(get_db),
):
    """Estimate property value based on address and characteristics."""
    if not request.address and not (request.lat and request.lon):
        raise HTTPException(
            status_code=400, detail="Provide either address or lat/lon coordinates"
        )

    service = ValuationService(db)
    result = await service.estimate(request)
    return result

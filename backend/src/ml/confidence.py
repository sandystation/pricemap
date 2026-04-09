from datetime import datetime, timedelta

from geoalchemy2.functions import ST_MakePoint, ST_SetSRID
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.country import Country
from src.models.property import Property
from src.schemas.valuation import ValuationRequest


class ConfidenceScorer:
    """Calculate confidence score (0-100) for a valuation."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def score(
        self,
        country_code: str,
        lat: float,
        lon: float,
        num_comparables: int,
        request: ValuationRequest,
    ) -> float:
        # Data density (40% weight): comparable transactions within 2km and 12 months
        density_score = await self._density_score(country_code, lat, lon)

        # Feature completeness (20% weight): how many optional fields filled
        completeness_score = self._completeness_score(request)

        # Model certainty proxy (25% weight): based on number of comparables found
        certainty_score = self._certainty_score(num_comparables)

        # Data freshness (15% weight): age of most recent comparable
        freshness_score = await self._freshness_score(country_code, lat, lon)

        total = (
            density_score * 0.40
            + completeness_score * 0.20
            + certainty_score * 0.25
            + freshness_score * 0.15
        )

        return round(min(max(total, 0), 100), 1)

    async def _density_score(
        self, country_code: str, lat: float, lon: float
    ) -> float:
        """Score based on number of properties within 2km."""
        country = await self.db.scalar(
            select(Country).where(Country.code == country_code.upper())
        )
        if not country:
            return 0

        point = ST_SetSRID(ST_MakePoint(lon, lat), 4326)
        one_year_ago = datetime.utcnow() - timedelta(days=365)

        count = await self.db.scalar(
            select(func.count(Property.id)).where(
                Property.country_id == country.id,
                Property.price_adjusted_eur.isnot(None),
                Property.geometry.ST_DWithin(point.cast_to("geography"), 2000),
                Property.created_at >= one_year_ago,
            )
        )

        # 0 comparables = 0, 5 = 50, 10+ = 100
        return min((count or 0) * 10, 100)

    def _completeness_score(self, request: ValuationRequest) -> float:
        """Score based on how many optional fields are filled."""
        optional_fields = [
            request.floor,
            request.rooms,
            request.bedrooms,
            request.bathrooms,
            request.year_built,
            request.condition,
            request.has_parking,
            request.has_garden,
            request.has_pool,
            request.has_elevator,
            request.has_balcony,
        ]
        filled = sum(1 for f in optional_fields if f is not None)
        return (filled / len(optional_fields)) * 100

    def _certainty_score(self, num_comparables: int) -> float:
        """Score based on number of comparables found."""
        # 0 = 0, 3 = 50, 5+ = 80, 10+ = 100
        if num_comparables >= 10:
            return 100
        elif num_comparables >= 5:
            return 80
        elif num_comparables >= 3:
            return 50
        elif num_comparables >= 1:
            return 25
        return 0

    async def _freshness_score(
        self, country_code: str, lat: float, lon: float
    ) -> float:
        """Score based on age of most recent comparable within 5km."""
        country = await self.db.scalar(
            select(Country).where(Country.code == country_code.upper())
        )
        if not country:
            return 0

        point = ST_SetSRID(ST_MakePoint(lon, lat), 4326)

        latest = await self.db.scalar(
            select(func.max(Property.scraped_at)).where(
                Property.country_id == country.id,
                Property.price_adjusted_eur.isnot(None),
                Property.geometry.ST_DWithin(point.cast_to("geography"), 5000),
            )
        )

        if not latest:
            return 0

        days_old = (datetime.utcnow() - latest).days
        # 0 days = 100, 30 days = 75, 90 days = 50, 180+ days = 10
        if days_old <= 7:
            return 100
        elif days_old <= 30:
            return 75
        elif days_old <= 90:
            return 50
        elif days_old <= 180:
            return 25
        return 10

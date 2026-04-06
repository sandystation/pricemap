from geoalchemy2.functions import ST_Distance, ST_MakePoint, ST_SetSRID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.country import Country
from src.models.property import Property
from src.schemas.valuation import ComparableProperty


class ComparableFinder:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def find(
        self,
        country_code: str,
        lat: float,
        lon: float,
        property_type: str,
        area_sqm: float,
        radius_km: float | None = None,
        max_count: int | None = None,
    ) -> list[ComparableProperty]:
        """Find comparable properties near a location."""
        radius = (radius_km or settings.comparable_radius_km) * 1000  # to meters
        limit = max_count or settings.comparable_max_count

        country = await self.db.scalar(
            select(Country).where(Country.code == country_code.upper())
        )
        if not country:
            return []

        point = ST_SetSRID(ST_MakePoint(lon, lat), 4326)
        distance = ST_Distance(
            Property.geometry.cast_to("geography"),
            point.cast_to("geography"),
        )

        # Area tolerance: +/- 30%
        min_area = area_sqm * 0.7
        max_area = area_sqm * 1.3

        query = (
            select(Property, distance.label("distance_m"))
            .where(
                Property.country_id == country.id,
                Property.property_type == property_type,
                Property.area_sqm.between(min_area, max_area),
                Property.price_adjusted_eur.isnot(None),
                Property.geometry.ST_DWithin(
                    point.cast_to("geography"),
                    radius,
                ),
            )
            .order_by(distance)
            .limit(limit)
        )

        result = await self.db.execute(query)
        rows = result.all()

        comparables = []
        for prop, dist_m in rows:
            price_per_sqm = (
                prop.price_adjusted_eur / prop.area_sqm
                if prop.area_sqm and prop.price_adjusted_eur
                else 0
            )
            comparables.append(
                ComparableProperty(
                    id=prop.id,
                    address=prop.address_normalized or prop.address_raw,
                    lat=prop.lat,
                    lon=prop.lon,
                    property_type=prop.property_type.value,
                    area_sqm=prop.area_sqm,
                    price_eur=prop.price_adjusted_eur or prop.price_eur,
                    price_per_sqm=round(price_per_sqm, 2),
                    distance_m=round(float(dist_m), 1),
                    listing_date=(
                        prop.listing_date.isoformat() if prop.listing_date else None
                    ),
                    source=prop.source.value,
                )
            )

        return comparables

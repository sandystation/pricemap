from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.country import Country, Region
from src.models.price_index import PriceIndex
from src.models.property import Property


class StatsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_stats(self, country_code: str, region: str | None = None) -> dict:
        country = await self.db.scalar(
            select(Country).where(Country.code == country_code.upper())
        )
        if not country:
            return {"error": "Country not found"}

        # Aggregate property stats
        query = select(
            func.count(Property.id).label("total_properties"),
            func.avg(Property.price_adjusted_eur).label("avg_price"),
            func.avg(
                Property.price_adjusted_eur / func.nullif(Property.area_sqm, 0)
            ).label("avg_price_per_sqm"),
            func.min(Property.price_adjusted_eur).label("min_price"),
            func.max(Property.price_adjusted_eur).label("max_price"),
        ).where(
            Property.country_id == country.id,
            Property.is_active.is_(True),
            Property.price_adjusted_eur.isnot(None),
        )

        result = await self.db.execute(query)
        stats = result.one()

        # Latest price index
        latest_index = await self.db.scalar(
            select(PriceIndex)
            .where(PriceIndex.country_id == country.id)
            .order_by(PriceIndex.year.desc(), PriceIndex.quarter.desc())
            .limit(1)
        )

        return {
            "country_code": country_code.upper(),
            "total_properties": stats.total_properties,
            "avg_price_eur": round(stats.avg_price, 2) if stats.avg_price else None,
            "avg_price_per_sqm": (
                round(stats.avg_price_per_sqm, 2) if stats.avg_price_per_sqm else None
            ),
            "min_price_eur": stats.min_price,
            "max_price_eur": stats.max_price,
            "latest_index": {
                "quarter": latest_index.quarter,
                "value": latest_index.index_value,
                "source": latest_index.source,
            }
            if latest_index
            else None,
        }

    async def get_heatmap(self, country_code: str) -> dict:
        country = await self.db.scalar(
            select(Country).where(Country.code == country_code.upper())
        )
        if not country:
            return {"type": "FeatureCollection", "features": []}

        # Get regions with avg price per sqm
        query = (
            select(
                Region.name,
                Region.geometry.ST_AsGeoJSON().label("geojson"),
                func.avg(
                    Property.price_adjusted_eur / func.nullif(Property.area_sqm, 0)
                ).label("avg_price_per_sqm"),
                func.count(Property.id).label("count"),
            )
            .join(Property, Property.region_id == Region.id)
            .where(
                Region.country_id == country.id,
                Property.price_adjusted_eur.isnot(None),
                Property.is_active.is_(True),
            )
            .group_by(Region.id, Region.name, Region.geometry)
        )

        result = await self.db.execute(query)
        rows = result.all()

        import json

        features = []
        for row in rows:
            if row.geojson:
                features.append(
                    {
                        "type": "Feature",
                        "geometry": json.loads(row.geojson),
                        "properties": {
                            "name": row.name,
                            "avg_price_per_sqm": (
                                round(row.avg_price_per_sqm, 2)
                                if row.avg_price_per_sqm
                                else None
                            ),
                            "count": row.count,
                        },
                    }
                )

        return {"type": "FeatureCollection", "features": features}

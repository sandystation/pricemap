from fastapi import HTTPException
from geoalchemy2.functions import ST_MakeEnvelope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.country import Country
from src.models.property import Property
from src.schemas.property import PropertyListResponse, PropertyResponse


class PropertyService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def search(
        self,
        country_code: str,
        min_lat: float,
        max_lat: float,
        min_lon: float,
        max_lon: float,
        property_type: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        limit: int = 100,
    ) -> PropertyListResponse:
        country = await self.db.scalar(
            select(Country).where(Country.code == country_code.upper())
        )
        if not country:
            raise HTTPException(status_code=404, detail="Country not found")

        bbox = ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, 4326)

        query = (
            select(Property)
            .where(
                Property.country_id == country.id,
                Property.geometry.ST_Within(bbox),
                Property.is_active.is_(True),
            )
            .limit(limit)
        )

        if property_type:
            query = query.where(Property.property_type == property_type)
        if min_price is not None:
            query = query.where(Property.price_adjusted_eur >= min_price)
        if max_price is not None:
            query = query.where(Property.price_adjusted_eur <= max_price)

        result = await self.db.execute(query)
        properties = result.scalars().all()

        items = [self._to_response(p, country_code) for p in properties]
        return PropertyListResponse(items=items, total=len(items))

    async def get_by_id(self, property_id: int) -> PropertyResponse:
        prop = await self.db.get(Property, property_id)
        if not prop:
            raise HTTPException(status_code=404, detail="Property not found")

        country = await self.db.get(Country, prop.country_id)
        if not country:
            raise HTTPException(status_code=404, detail="Country not found")
        return self._to_response(prop, country.code)

    def _to_response(self, prop: Property, country_code: str) -> PropertyResponse:
        price_per_sqm = None
        if prop.price_adjusted_eur and prop.area_sqm:
            price_per_sqm = round(prop.price_adjusted_eur / prop.area_sqm, 2)

        return PropertyResponse(
            id=prop.id,
            country_code=country_code,
            address=prop.address_normalized or prop.address_raw,
            locality=prop.locality,
            lat=prop.lat,
            lon=prop.lon,
            property_type=prop.property_type.value,
            area_sqm=prop.area_sqm,
            floor=prop.floor,
            rooms=prop.rooms,
            bedrooms=prop.bedrooms,
            year_built=prop.year_built,
            condition=prop.condition.value if prop.condition else None,
            price_eur=prop.price_adjusted_eur or prop.price_eur,
            price_per_sqm=price_per_sqm,
            price_type=prop.price_type.value,
            source=prop.source.value,
            listing_date=prop.listing_date.isoformat() if prop.listing_date else None,
            is_active=prop.is_active,
        )

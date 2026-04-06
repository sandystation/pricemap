import json

from geopy.adapters import AioHTTPAdapter
from geopy.geocoders import Nominatim

from src.config import settings
from src.core.redis import redis_client
from src.schemas.geocode import GeocodeResponse

COUNTRY_CODES = {
    "MT": "Malta",
    "BG": "Bulgaria",
    "CY": "Cyprus",
    "HR": "Croatia",
}


class GeocodingService:
    async def geocode(self, address: str, country_code: str) -> GeocodeResponse:
        country_code = country_code.upper()
        cache_key = f"geocode:{country_code}:{address.lower().strip()}"

        # Check cache
        cached = await redis_client.get(cache_key)
        if cached:
            return GeocodeResponse(**json.loads(cached))

        # Geocode with Nominatim
        country_name = COUNTRY_CODES.get(country_code, "")
        query = f"{address}, {country_name}" if country_name else address

        async with Nominatim(
            user_agent=settings.nominatim_user_agent,
            adapter_factory=AioHTTPAdapter,
        ) as geolocator:
            location = await geolocator.geocode(
                query, exactly_one=True, addressdetails=True
            )

        if not location:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Address not found")

        # Extract locality from address details
        raw = location.raw.get("address", {})
        locality = (
            raw.get("city")
            or raw.get("town")
            or raw.get("village")
            or raw.get("municipality")
        )

        result = GeocodeResponse(
            lat=location.latitude,
            lon=location.longitude,
            display_name=location.address,
            locality=locality,
            confidence=1.0 if location.raw.get("importance", 0) > 0.5 else 0.7,
        )

        # Cache result
        await redis_client.set(
            cache_key, result.model_dump_json(), ex=settings.geocode_cache_ttl
        )

        return result

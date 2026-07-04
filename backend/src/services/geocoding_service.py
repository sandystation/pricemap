import json

from geopy.adapters import AioHTTPAdapter
from geopy.geocoders import Nominatim
from redis import Redis

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

    def geocode_sync(self, address: str, country_code: str) -> GeocodeResponse:
        """Synchronous geocode for the Celery worker (sync context).

        Uses a per-call sync Redis client and geopy's sync Nominatim — avoids the
        asyncio-per-task event-loop reuse that breaks the module-level async Redis
        client across successive jobs. Falls back to an address-only query so an
        address that already contains the country still resolves.
        """
        from fastapi import HTTPException

        country_code = country_code.upper()
        cache_key = f"geocode:{country_code}:{address.lower().strip()}"
        client = Redis.from_url(settings.redis_url, decode_responses=True)
        try:
            cached = client.get(cache_key)
            if isinstance(cached, (str, bytes, bytearray)):
                return GeocodeResponse(**json.loads(cached))

            country_name = COUNTRY_CODES.get(country_code, "")
            geolocator = Nominatim(user_agent=settings.nominatim_user_agent)
            queries = [f"{address}, {country_name}", address] if country_name else [address]
            location = None
            for q in queries:
                location = geolocator.geocode(q, exactly_one=True, addressdetails=True, timeout=15)
                if location:
                    break
            if not location:
                raise HTTPException(status_code=404, detail="Address not found")

            raw = location.raw.get("address", {})
            locality = (
                raw.get("city") or raw.get("town")
                or raw.get("village") or raw.get("municipality")
            )
            result = GeocodeResponse(
                lat=location.latitude,
                lon=location.longitude,
                display_name=location.address,
                locality=locality,
                confidence=1.0 if location.raw.get("importance", 0) > 0.5 else 0.7,
            )
            client.set(cache_key, result.model_dump_json(), ex=settings.geocode_cache_ttl)
            return result
        finally:
            client.close()

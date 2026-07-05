import json

from geopy.adapters import AioHTTPAdapter
from geopy.geocoders import Nominatim, Photon
from redis import Redis

from src.config import settings
from src.core.redis import redis_client
from src.schemas.geocode import GeocodeCandidate, GeocodeResponse

COUNTRY_CODES = {
    "MT": "Malta",
    "BG": "Bulgaria",
    "CY": "Cyprus",
    "HR": "Croatia",
}

# Malta bounding box (SW, NE) + ranking bias for typeahead search, as (lat, lon).
MALTA_BBOX = [(35.79, 14.18), (36.09, 14.58)]
MALTA_CENTER = (35.9, 14.45)


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

    async def search(
        self, q: str, country_code: str, limit: int = 6
    ) -> list[GeocodeCandidate]:
        """Typeahead address suggestions (Malta only) via Photon.

        Photon (photon.komoot.io) is OSM-based and built for autocomplete; Nominatim's
        usage policy forbids typeahead, so it is NOT used here. Degrades to an empty
        list on any upstream failure so the form falls back to free-typed address.
        """
        country_code = country_code.upper()
        if country_code != "MT":
            return []  # feature is Malta-only for now

        q = q.strip()
        cache_key = f"geosearch:{country_code}:{q.lower()}:{limit}"
        cached = await redis_client.get(cache_key)
        if cached:
            return [GeocodeCandidate(**c) for c in json.loads(cached)]

        try:
            async with Photon(
                user_agent=settings.nominatim_user_agent,
                adapter_factory=AioHTTPAdapter,
            ) as geolocator:
                locations = await geolocator.geocode(
                    q,
                    exactly_one=False,
                    limit=limit,
                    location_bias=MALTA_CENTER,
                    bbox=MALTA_BBOX,
                    timeout=8,
                )
        except Exception:
            return []

        candidates: list[GeocodeCandidate] = []
        for loc in locations or []:
            props = loc.raw.get("properties", {}) if isinstance(loc.raw, dict) else {}
            # Belt-and-suspenders: the bbox already clips to Malta, but drop anything
            # Photon tags with a non-MT country.
            if str(props.get("countrycode", "")).upper() not in ("", "MT"):
                continue
            locality = (
                props.get("city")
                or props.get("town")
                or props.get("village")
                or props.get("county")
            )
            candidates.append(
                GeocodeCandidate(
                    lat=loc.latitude,
                    lon=loc.longitude,
                    display_name=loc.address,
                    locality=locality,
                )
            )

        await redis_client.set(
            cache_key,
            json.dumps([c.model_dump() for c in candidates]),
            ex=settings.geocode_cache_ttl,
        )
        return candidates

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
